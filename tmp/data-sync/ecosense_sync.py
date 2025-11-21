#!/usr/bin/env python3
"""
Unified Ecosense Data Sync Script

Single script that connects to Aquarius, filters to only sensors used by the Shiny app,
and pushes data directly to the production server. No local database dependency.

Usage:
  python ecosense_sync.py                    # Sync last 7 days of data
  python ecosense_sync.py --test            # Test all connections
  python ecosense_sync.py --days 30         # Sync last 30 days
  python ecosense_sync.py --dry-run         # Show what would be synced
  python ecosense_sync.py --use-inventory   # Enable smart filtering via local DB
"""

import argparse
import logging
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("ecosense_sync.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


@dataclass
class EcosenseSensor:
    """Represents a sensor needed by the Shiny app"""

    label: str
    location_identifier: str
    parameter: str
    parameter_unit: str
    timeseries_identifier: str  # parameter.label@location_identifier
    unique_id: str


class AquariusClient:
    """Official Aquarius API client for sensor discovery and data retrieval"""

    def __init__(self, hostname: str, username: str, password: str):
        self.hostname = hostname.rstrip("/")
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.token = None

        # Handle hostname that may or may not include /AQUARIUS
        if "/AQUARIUS" in self.hostname:
            self.base_url = f"{self.hostname}/Publish/v2"
        else:
            self.base_url = f"{self.hostname}/AQUARIUS/Publish/v2"

    def connect(self) -> bool:
        """Connect to Aquarius API"""
        try:
            auth_url = f"{self.base_url}/session"
            logger.info(f"Connecting to Aquarius at: {auth_url}")

            response = self.session.post(
                auth_url,
                json={
                    "Username": self.username,
                    "EncryptedPassword": self.password,
                },
                timeout=30,
            )

            if response.status_code == 200:
                self.token = response.text.strip('\\"')
                self.session.headers.update({"X-Authentication-Token": self.token})
                logger.info("✅ Connected to Aquarius successfully")
                return True
            else:
                logger.error(
                    f"❌ Aquarius connection failed: {response.status_code} - {response.text}"
                )
                return False

        except Exception as e:
            logger.error(f"❌ Aquarius connection error: {e}")
            return False

    def disconnect(self):
        """Disconnect from Aquarius"""
        try:
            if self.token:
                self.session.delete(f"{self.base_url}/session")
                logger.info("Disconnected from Aquarius")
        except Exception as e:
            logger.warning(f"Disconnect warning: {e}")

    def get_ecosense_sensors(
        self, use_inventory_filtering: bool = False
    ) -> List[EcosenseSensor]:
        """Get sensors needed by the Shiny app with optional smart filtering"""

        # Parameters that the R Shiny app uses
        TARGET_PARAMETERS = {
            "Sapflow",
            "StemRadialVar_Volt",
            "BarPressure",
            "SoilMoisture",
            "SoilTemp",
        }

        # Smart filtering: Get exact sensors that Shiny app uses
        if use_inventory_filtering:
            try:
                conn = psycopg2.connect(
                    host=os.getenv("LOCAL_DB_HOST", "localhost"),
                    port=int(os.getenv("LOCAL_DB_PORT", "5432")),
                    database=os.getenv("LOCAL_DB_NAME", "sensors"),
                    user=os.getenv("LOCAL_DB_USER", "postgres"),
                    password=os.getenv("LOCAL_DB_PASSWORD", "postgres"),
                )

                # Get the sensors that Shiny app actually uses (first sensor per parameter per tree)
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT DISTINCT s.label, s.locationidentifier, s.parameter, s.parameterunit,
                               l.aquariusname,
                               ROW_NUMBER() OVER (PARTITION BY l.plot_id, l.tree_id, s.parameter ORDER BY s.label) AS rn
                        FROM ecosense.link_sensors_trees_inventory l
                        JOIN ecosense.ecosense_sensors s ON s.label ILIKE l.aquariusname || %s
                        WHERE s.parameter IN ('Sapflow', 'StemRadialVar_Volt', 'BarPressure', 'SoilMoisture', 'SoilTemp')
                    """,
                        ("%",),
                    )

                    shiny_sensors = cursor.fetchall()

                    # Filter to only the sensors Shiny actually uses (rn = 1)
                    actual_sensors = [
                        (label, location, param, unit, aq_name)
                        for label, location, param, unit, aq_name, rn in shiny_sensors
                        if rn == 1
                    ]

                    logger.info(
                        f"🎯 Smart filtering: Found {len(actual_sensors)} sensors actually used by Shiny app"
                    )

                    # Get all time series descriptions ONCE (instead of per sensor)
                    logger.info("📥 Fetching Aquarius time series descriptions...")
                    response = self.session.get(
                        f"{self.base_url}/GetTimeSeriesDescriptionList", timeout=30
                    )

                    if response.status_code != 200:
                        logger.error(
                            f"Failed to get time series descriptions: {response.status_code}"
                        )
                        return []

                    all_ts = response.json().get("TimeSeriesDescriptions", [])
                    logger.info(
                        f"📊 Retrieved {len(all_ts)} time series descriptions from Aquarius"
                    )

                    # Create sensor objects directly from this precise list
                    sensors = []
                    for i, (label, location, param, unit, aq_name) in enumerate(
                        actual_sensors, 1
                    ):
                        ts_identifier = f"{param}.{label}@{location}"

                        # Progress indicator for sensor processing
                        if i % 10 == 0 or i == len(actual_sensors):
                            logger.info(
                                f"  🔍 Processing sensor {i}/{len(actual_sensors)}: {ts_identifier}"
                            )

                        # Find unique ID from the already-fetched time series list
                        unique_id = None
                        for ts in all_ts:
                            if (
                                ts.get("Parameter") == param
                                and ts.get("Label") == label
                                and ts.get("LocationIdentifier") == location
                            ):
                                unique_id = ts.get("UniqueId")
                                break

                        if unique_id:
                            sensor = EcosenseSensor(
                                label=label,
                                location_identifier=location,
                                parameter=param,
                                parameter_unit=unit,
                                timeseries_identifier=ts_identifier,
                                unique_id=unique_id,
                            )
                            sensors.append(sensor)
                        else:
                            logger.warning(
                                f"⚠️  Could not find unique_id for {ts_identifier} in Aquarius"
                            )

                conn.close()

                # Log summary by parameter
                by_param = {}
                for sensor in sensors:
                    by_param.setdefault(sensor.parameter, 0)
                    by_param[sensor.parameter] += 1

                for param, count in sorted(by_param.items()):
                    logger.info(f"   {param}: {count} sensors")

                logger.info(
                    f"🎯 Exact Shiny app filtering: {len(sensors)} sensors (much more efficient!)"
                )
                return sensors

            except Exception as e:
                logger.warning(
                    f"⚠️  Could not connect to local DB for smart filtering: {e}"
                )
                logger.info("Falling back to basic Ecosense filtering...")
                use_inventory_filtering = False

        # Fallback: Basic filtering (all Ecosense sensors for target parameters)
        logger.info(
            "📈 Using basic filtering (all Ecosense sensors for target parameters)"
        )

        # Get all time series descriptions
        try:
            response = self.session.get(
                f"{self.base_url}/GetTimeSeriesDescriptionList", timeout=30
            )
            if response.status_code != 200:
                logger.error(
                    f"Failed to get time series descriptions: {response.status_code}"
                )
                return []

            all_series = response.json().get("TimeSeriesDescriptions", [])
            ecosense_series = [
                ts
                for ts in all_series
                if ts.get("LocationIdentifier", "").startswith("Ecosense_")
            ]

            logger.info(
                f"📊 Found {len(ecosense_series)} Ecosense time series out of {len(all_series)} total"
            )

        except Exception as e:
            logger.error(f"Error getting time series descriptions: {e}")
            return []

        # Filter and create sensor objects
        sensors = []

        for ts in ecosense_series:
            parameter = ts.get("Parameter", "")
            location_id = ts.get("LocationIdentifier", "")
            label = ts.get("Label", "")
            unique_id = ts.get("UniqueId", "")
            unit = ts.get("Unit", "")

            # Only include parameters that the R app uses
            if parameter in TARGET_PARAMETERS:
                # Create sensor object
                ts_identifier = f"{parameter}.{label}@{location_id}"
                sensor = EcosenseSensor(
                    label=label,
                    location_identifier=location_id,
                    parameter=parameter,
                    parameter_unit=unit,
                    timeseries_identifier=ts_identifier,
                    unique_id=unique_id,
                )
                sensors.append(sensor)

        logger.info(
            f"📈 Basic filtering: found {len(sensors)} Ecosense sensors for target parameters"
        )

        # Log summary by parameter
        by_param = {}
        for sensor in sensors:
            by_param.setdefault(sensor.parameter, 0)
            by_param[sensor.parameter] += 1

        for param, count in sorted(by_param.items()):
            logger.info(f"   {param}: {count} sensors")

        return sensors

    def get_sensor_data(
        self, sensor: EcosenseSensor, start_time: datetime, end_time: datetime
    ) -> List[Dict[str, Any]]:
        """Get time series data for a sensor"""
        try:
            # Format timestamps as ISO 8601
            start_str = start_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
            end_str = end_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

            params = {
                "TimeSeriesUniqueId": sensor.unique_id,
                "QueryFrom": start_str,
                "QueryTo": end_str,
            }

            response = self.session.get(
                f"{self.base_url}/GetTimeSeriesCorrectedData", params=params, timeout=60
            )

            if response.status_code != 200:
                logger.warning(
                    f"⚠️  Failed to get data for {sensor.timeseries_identifier}: {response.status_code}"
                )
                return []

            ts_data = response.json()
            points = ts_data.get("Points", [])

            # Convert to standard format
            data_points = []
            for point in points:
                if (
                    "Value" in point
                    and "Numeric" in point["Value"]
                    and point["Value"]["Numeric"] is not None
                ):

                    timestamp = datetime.fromisoformat(
                        point["Timestamp"].replace("Z", "+00:00")
                    )
                    value = float(point["Value"]["Numeric"])

                    data_points.append(
                        {
                            "timeseries_id": sensor.timeseries_identifier,
                            "timestamp": timestamp.isoformat(),
                            "value": value,
                            "parameter": sensor.parameter,
                            "sensor_label": sensor.label,
                            "location_identifier": sensor.location_identifier,
                        }
                    )

            return data_points

        except Exception as e:
            logger.error(
                f"❌ Error getting data for {sensor.timeseries_identifier}: {e}"
            )
            return []


class LocalDatabaseSync:
    """Handles local database operations for staging data"""

    def __init__(self):
        self.host = os.getenv("LOCAL_DB_HOST", "localhost")
        self.port = int(os.getenv("LOCAL_DB_PORT", "5432"))
        self.database = os.getenv("LOCAL_DB_NAME", "sensors")
        self.user = os.getenv("LOCAL_DB_USER", "postgres")
        self.password = os.getenv("LOCAL_DB_PASSWORD", "postgres")

        logger.info(
            f"🗄️  Local database sync initialized: {self.host}:{self.port}/{self.database}"
        )

    def get_connection(self):
        """Get database connection"""
        return psycopg2.connect(
            host=self.host,
            port=self.port,
            database=self.database,
            user=self.user,
            password=self.password,
        )

    def test_connection(self) -> bool:
        """Test local database connection"""
        try:
            conn = self.get_connection()
            conn.close()
            logger.info("✅ Local database connection successful")
            return True
        except Exception as e:
            logger.error(f"❌ Local database connection failed: {e}")
            return False

    def bulk_insert_local(self, data_points: List[Dict[str, Any]]) -> bool:
        """Insert data points into local database with high performance"""
        if not data_points:
            return True

        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Prepare data for bulk insertion
            data_tuples = [
                (
                    point["timeseries_id"],
                    point["timestamp"],
                    point["value"],
                    point["parameter"],
                    point["sensor_label"],
                    point["location_identifier"],
                )
                for point in data_points
            ]

            # Use execute_values for high performance bulk insert
            insert_query = """
                INSERT INTO ecosense.timeseries_data 
                (timeseries_id, timestamp, value, parameter, sensor_label, location_identifier)
                VALUES %s
                ON CONFLICT (timeseries_id, timestamp) 
                DO UPDATE SET 
                    value = EXCLUDED.value,
                    updated_at = NOW()
            """

            psycopg2.extras.execute_values(
                cursor, insert_query, data_tuples, page_size=5000
            )

            conn.commit()
            cursor.close()
            conn.close()

            logger.info(f"✅ Local DB: {len(data_points)} points inserted/updated")
            return True

        except Exception as e:
            logger.error(f"❌ Local database insert failed: {e}")
            if conn:
                try:
                    conn.rollback()
                    conn.close()
                except Exception:
                    pass
            return False

    def get_unsent_data(
        self,
        batch_size: int = 1000,
        timeseries_id: Optional[str] = None,
        days_back: Optional[int] = 7,
    ) -> List[Dict[str, Any]]:
        """Get data that hasn't been sent to production yet"""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            # Query for unsent data - you could add a 'sent_to_production' flag if needed
            # For now, we'll get recent data and let production handle duplicates
            if days_back is None:
                # Get all data - but limit to reasonable batch size to prevent memory issues
                base_query = """
                    SELECT timeseries_id, timestamp, value, parameter, sensor_label, location_identifier
                    FROM ecosense.timeseries_data
                """
                # For ALL data mode, use a larger but still manageable batch size
                effective_batch_size = min(
                    batch_size * 50, 50000
                )  # Max 50k records at once
                logger.info(
                    f"📊 ALL DATA mode: limiting to {effective_batch_size:,} records per batch to prevent memory issues"
                )
            else:
                # Get data from last N days
                base_query = f"""
                    SELECT timeseries_id, timestamp, value, parameter, sensor_label, location_identifier
                    FROM ecosense.timeseries_data
                    WHERE created_at >= NOW() - INTERVAL '{days_back} days'
                """
                effective_batch_size = batch_size

            if timeseries_id:
                base_query += " AND timeseries_id = %s"
                cursor.execute(
                    base_query + " ORDER BY timestamp DESC LIMIT %s",
                    (timeseries_id, effective_batch_size),
                )
            else:
                # Always use LIMIT to prevent memory exhaustion
                cursor.execute(
                    base_query + " ORDER BY timestamp DESC LIMIT %s",
                    (effective_batch_size,),
                )

            rows = cursor.fetchall()
            cursor.close()
            conn.close()

            logger.info(f"📥 Retrieved {len(rows):,} data points from local database")

            # Convert to list of dicts
            data_points = []
            for row in rows:
                data_points.append(
                    {
                        "timeseries_id": row["timeseries_id"],
                        "timestamp": row["timestamp"].isoformat(),
                        "value": float(row["value"]),
                        "parameter": row["parameter"],
                        "sensor_label": row["sensor_label"],
                        "location_identifier": row["location_identifier"],
                    }
                )

            return data_points

        except Exception as e:
            logger.error(f"❌ Error fetching unsent data: {e}")
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
            return []

    def get_local_stats(self) -> Dict[str, Any]:
        """Get statistics about local database"""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            cursor.execute(
                """
                SELECT 
                    parameter,
                    COUNT(*) as total_points,
                    MIN(timestamp) as earliest,
                    MAX(timestamp) as latest,
                    COUNT(DISTINCT timeseries_id) as unique_series
                FROM ecosense.timeseries_data 
                GROUP BY parameter
                ORDER BY parameter
            """
            )

            stats = cursor.fetchall()
            cursor.close()
            conn.close()

            return {"stats": [dict(stat) for stat in stats]}

        except Exception as e:
            logger.error(f"❌ Error getting local stats: {e}")
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
            return {"stats": []}


class ProductionClient:
    """HTTP client for pushing data to production server with adaptive rate limiting"""

    def __init__(self):
        self.remote_host = os.getenv("REMOTE_DB_HOST", "dt.unr.uni-freiburg.de")
        self.api_token = os.getenv("PG_PROXY_TOKEN")

        if not self.api_token:
            raise ValueError("PG_PROXY_TOKEN environment variable is required")

        self.base_url = f"https://{self.remote_host}/api/db"
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

        # Adaptive rate limiting parameters - optimized for large syncs
        self.base_batch_size = 1000  # Increased from 500
        self.current_batch_size = self.base_batch_size
        self.base_delay = 0.6  # Reduced from 1.0 seconds (just under 60/min limit)
        self.current_delay = self.base_delay
        self.max_retries = 5
        self.backoff_multiplier = 2.0
        self.success_count = 0
        self.failure_count = 0

        logger.info(f"📡 Production client initialized: {self.base_url}")

    def test_connection(self) -> bool:
        """Test connection to production server"""
        try:
            response = requests.get(
                f"{self.base_url}/health", headers=self.headers, timeout=30
            )
            if response.status_code == 200:
                logger.info("✅ Production server connection successful")
                return True
            else:
                logger.error(
                    f"❌ Production health check failed: {response.status_code}"
                )
                return False
        except Exception as e:
            logger.error(f"❌ Production connection test failed: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get production database statistics"""
        try:
            response = requests.get(
                f"{self.base_url}/timeseries/stats", headers=self.headers, timeout=30
            )
            if response.status_code == 200:
                return response.json()
            return {}
        except Exception as e:
            logger.error(f"Error getting production stats: {e}")
            return {}

    def _adaptive_delay(self, success: bool, was_rate_limited: bool = False):
        """Adjust delay and batch size based on success/failure patterns"""
        if success and not was_rate_limited:
            self.success_count += 1
            self.failure_count = 0

            # Gradually reduce delay and increase batch size on success
            if self.success_count >= 3:
                self.current_delay = max(0.5, self.current_delay * 0.9)
                self.current_batch_size = min(
                    5000, int(self.current_batch_size * 1.1)
                )  # Increased max to 5000
                self.success_count = 0

        elif was_rate_limited:
            self.failure_count += 1
            self.success_count = 0

            # Aggressive backoff on rate limiting
            self.current_delay = min(60.0, self.current_delay * self.backoff_multiplier)
            self.current_batch_size = max(
                200, int(self.current_batch_size * 0.5)
            )  # Increased min to 200

            logger.warning(
                f"⚠️  Rate limited! Adjusting: delay={self.current_delay:.1f}s, batch_size={self.current_batch_size}"
            )
        else:
            self.failure_count += 1
            self.success_count = 0

            # Moderate backoff on other errors
            self.current_delay = min(30.0, self.current_delay * 1.5)

        logger.debug(
            f"Adaptive settings: delay={self.current_delay:.1f}s, batch_size={self.current_batch_size}"
        )

    def bulk_insert(
        self, data_points: List[Dict[str, Any]], batch_size: Optional[int] = None
    ) -> bool:
        """Send data points to production server with adaptive rate limiting and exponential backoff"""
        if not data_points:
            return True

        # Use adaptive batch size unless explicitly overridden
        effective_batch_size = batch_size or self.current_batch_size

        try:
            total_points = len(data_points)
            total_sent = 0

            # Process in batches with adaptive rate limiting
            for i in range(0, total_points, effective_batch_size):
                batch = data_points[i : i + effective_batch_size]
                batch_success = False

                # Retry logic for each batch
                for attempt in range(self.max_retries):
                    try:
                        payload = {"data_points": batch}
                        response = requests.post(
                            f"{self.base_url}/timeseries/bulk-insert",
                            headers=self.headers,
                            json=payload,
                            timeout=120,
                        )

                        if response.status_code == 200:
                            result = response.json()
                            batch_sent = result.get("inserted_count", len(batch))
                            total_sent += batch_sent
                            logger.info(
                                f"   📤 Batch {i//effective_batch_size + 1}: {batch_sent} points sent (attempt {attempt + 1})"
                            )

                            # Adaptive delay adjustment
                            self._adaptive_delay(success=True, was_rate_limited=False)
                            batch_success = True
                            break

                        elif response.status_code == 429:
                            # Rate limit exceeded - exponential backoff
                            retry_delay = self.current_delay * (
                                self.backoff_multiplier**attempt
                            )
                            logger.warning(
                                f"❌ Rate limit exceeded! Waiting {retry_delay:.1f}s before retry {attempt + 1}/{self.max_retries}"
                            )

                            self._adaptive_delay(success=False, was_rate_limited=True)
                            time.sleep(retry_delay)
                            continue

                        else:
                            logger.error(
                                f"❌ Batch failed: {response.status_code} - {response.text[:200]}"
                            )
                            self._adaptive_delay(success=False, was_rate_limited=False)

                            if attempt < self.max_retries - 1:
                                time.sleep(self.current_delay * (1.5**attempt))
                                continue
                            else:
                                return False

                    except requests.exceptions.Timeout:
                        logger.warning(f"⏰ Request timeout on attempt {attempt + 1}")
                        if attempt < self.max_retries - 1:
                            time.sleep(self.current_delay * (1.5**attempt))
                            continue
                        else:
                            logger.error("❌ Max timeout retries exceeded")
                            return False

                    except Exception as e:
                        logger.error(
                            f"❌ Unexpected error on attempt {attempt + 1}: {e}"
                        )
                        if attempt < self.max_retries - 1:
                            time.sleep(self.current_delay)
                            continue
                        else:
                            return False

                if not batch_success:
                    logger.error(
                        f"❌ Failed to send batch after {self.max_retries} attempts"
                    )
                    return False

                # Adaptive delay between successful batches
                if i + effective_batch_size < total_points:
                    time.sleep(self.current_delay)

            logger.info(f"✅ Successfully sent {total_sent} data points to production")
            return True

        except Exception as e:
            logger.error(f"❌ Error sending data to production: {e}")
            return False


class EcosenseSync:
    """Main sync orchestrator with two-stage architecture"""

    def __init__(self):
        self.aquarius = AquariusClient(
            hostname=os.getenv("AQUARIUS_HOSTNAME", ""),
            username=os.getenv("AQUARIUS_USERNAME", ""),
            password=os.getenv("AQUARIUS_PASSWORD", ""),
        )
        self.local_db = LocalDatabaseSync()
        self.production = ProductionClient()

    def test_connections(self) -> bool:
        """Test all required connections"""
        logger.info("🔍 Testing connections...")

        all_good = True

        # Test Aquarius
        if self.aquarius.connect():
            logger.info("✅ Aquarius: Connected")
            self.aquarius.disconnect()
        else:
            logger.error("❌ Aquarius: Failed")
            all_good = False

        # Test Local Database
        if not self.local_db.test_connection():
            all_good = False

        # Test Production
        if not self.production.test_connection():
            all_good = False

        return all_good

    def sync_aquarius_to_local(
        self,
        days_back: int = 7,
        use_inventory: bool = False,
        dry_run: bool = False,
        specific_sensors: Optional[List[str]] = None,
    ) -> bool:
        """Stage 1: Sync data from Aquarius to local database"""

        logger.info(f"🚀 Stage 1: Aquarius → Local DB ({days_back} days)")
        start_time = datetime.now()

        # Connect to Aquarius
        if not self.aquarius.connect():
            logger.error("❌ Failed to connect to Aquarius")
            return False

        try:
            # Test local database connection
            if not self.local_db.test_connection():
                logger.error("❌ Failed to connect to local database")
                return False

            # Get sensors to sync
            sensors = self.aquarius.get_ecosense_sensors(
                use_inventory_filtering=use_inventory
            )
            if not sensors:
                logger.error("❌ No sensors found to sync")
                return False

            # Filter to specific sensors if requested
            if specific_sensors:
                sensors = [
                    s for s in sensors if s.timeseries_identifier in specific_sensors
                ]
                logger.info(f"🎯 Filtered to {len(sensors)} specific sensors")

            if dry_run:
                logger.info(
                    f"🏃 DRY RUN: Would sync {len(sensors)} sensors to local DB"
                )
                for sensor in sensors[:10]:  # Show first 10
                    logger.info(f"   - {sensor.timeseries_identifier}")
                if len(sensors) > 10:
                    logger.info(f"   ... and {len(sensors) - 10} more sensors")
                return True

            # Calculate time window
            end_time = datetime.now()
            start_sync_time = end_time - timedelta(days=days_back)

            logger.info(f"📅 Syncing data from {start_sync_time} to {end_time}")
            logger.info(f"📊 Processing {len(sensors)} sensors...")

            # Sync each sensor to local database
            success_count = 0
            total_points = 0

            for i, sensor in enumerate(sensors, 1):
                try:
                    # Progress indicator
                    progress = (i / len(sensors)) * 100
                    logger.info(
                        f"📊 [{i}/{len(sensors)}] ({progress:.1f}%) {sensor.parameter}.{sensor.label}"
                    )

                    # Get data from Aquarius
                    data_points = self.aquarius.get_sensor_data(
                        sensor, start_sync_time, end_time
                    )

                    if not data_points:
                        logger.info("   ⭕ No data points")
                        continue

                    # Send to local database (much faster, no rate limits)
                    if self.local_db.bulk_insert_local(data_points):
                        success_count += 1
                        total_points += len(data_points)
                        logger.info(f"   ✅ {len(data_points)} points stored locally")
                    else:
                        logger.warning(
                            f"   ❌ Failed to store {len(data_points)} points locally"
                        )

                    # Small delay to be nice to Aquarius
                    time.sleep(0.5)

                except Exception as e:
                    logger.error(f"   ❌ Error syncing sensor: {e}")

            # Final summary
            duration = datetime.now() - start_time
            logger.info("")
            logger.info("🎉 STAGE 1 COMPLETED!")
            logger.info(f"✅ Successful sensors: {success_count}/{len(sensors)}")
            logger.info(f"📊 Total data points: {total_points:,}")
            logger.info(f"⏱️  Duration: {duration}")

            return success_count > 0

        finally:
            self.aquarius.disconnect()

    def sync_local_to_production(
        self,
        batch_size: int = 1000,
        dry_run: bool = False,
        days_back: Optional[int] = None,
    ) -> bool:
        """Stage 2: Sync data from local database to production with pagination for large datasets"""

        logger.info(f"🚀 Stage 2: Local DB → Production (batch_size={batch_size})")
        if days_back is None:
            logger.info("📅 Syncing ALL historical data (with pagination)")
        else:
            logger.info(f"📅 Syncing last {days_back} days of data")

        start_time = datetime.now()

        try:
            # Test production connection
            if not self.production.test_connection():
                logger.error("❌ Failed to connect to production server")
                return False

            if days_back is None:
                # For ALL data mode, implement pagination to handle large datasets
                return self._sync_all_data_paginated(batch_size, dry_run)
            else:
                # For recent data, use the original approach
                data_points = self.local_db.get_unsent_data(
                    batch_size=batch_size * 10, days_back=days_back
                )

                if not data_points:
                    logger.info("📭 No data to sync to production")
                    return True

                if dry_run:
                    logger.info(
                        f"🏃 DRY RUN: Would sync {len(data_points)} points to production"
                    )
                    return True

                logger.info(
                    f"📊 Syncing {len(data_points)} data points to production..."
                )

                # Send to production with adaptive batching
                if self.production.bulk_insert(data_points, batch_size=batch_size):
                    duration = datetime.now() - start_time
                    logger.info("")
                    logger.info("🎉 STAGE 2 COMPLETED!")
                    logger.info(
                        f"✅ Successfully sent {len(data_points):,} points to production"
                    )
                    logger.info(f"⏱️  Duration: {duration}")
                    return True
                else:
                    logger.error("❌ Failed to sync data to production")
                    return False

        except Exception as e:
            logger.error(f"❌ Error in stage 2 sync: {e}")
            return False

    def _sync_all_data_paginated(self, batch_size: int, dry_run: bool) -> bool:
        """Handle syncing ALL historical data using pagination to prevent memory issues"""
        start_time = datetime.now()
        total_synced = 0
        page_size = 25000  # Process 25k records at a time
        offset = 0
        page_num = 1

        logger.info(f"📄 Using pagination: {page_size:,} records per page")

        try:
            while True:
                # Get a page of data
                conn = self.local_db.get_connection()
                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

                # Get count on first iteration
                if offset == 0:
                    cursor.execute(
                        "SELECT COUNT(*) as total FROM ecosense.timeseries_data"
                    )
                    count_result = cursor.fetchone()
                    total_count = count_result["total"] if count_result else 0
                    logger.info(f"📊 Total records to sync: {total_count:,}")

                    if dry_run:
                        cursor.close()
                        conn.close()
                        logger.info(
                            f"🏃 DRY RUN: Would sync {total_count:,} points to production in pages of {page_size:,}"
                        )
                        return True

                # Get the current page
                cursor.execute(
                    """
                    SELECT timeseries_id, timestamp, value, parameter, sensor_label, location_identifier
                    FROM ecosense.timeseries_data
                    ORDER BY timestamp DESC
                    LIMIT %s OFFSET %s
                """,
                    (page_size, offset),
                )

                rows = cursor.fetchall()
                cursor.close()
                conn.close()

                if not rows:
                    logger.info(f"📄 Page {page_num}: No more data to process")
                    break

                logger.info(
                    f"📄 Page {page_num}: Processing {len(rows):,} records (offset {offset:,})"
                )

                # Convert to the expected format
                data_points = []
                for row in rows:
                    data_points.append(
                        {
                            "timeseries_id": row["timeseries_id"],
                            "timestamp": row["timestamp"].isoformat(),
                            "value": float(row["value"]),
                            "parameter": row["parameter"],
                            "sensor_label": row["sensor_label"],
                            "location_identifier": row["location_identifier"],
                        }
                    )

                # Send this page to production
                if self.production.bulk_insert(data_points, batch_size=batch_size):
                    total_synced += len(data_points)
                    logger.info(
                        f"   ✅ Page {page_num} sent successfully. Total synced: {total_synced:,}"
                    )
                else:
                    logger.error(f"   ❌ Failed to send page {page_num}")
                    return False

                # Prepare for next page
                offset += page_size
                page_num += 1

                # Small delay between pages to be respectful
                time.sleep(1)

            # Final summary
            duration = datetime.now() - start_time
            logger.info("")
            logger.info("🎉 STAGE 2 COMPLETED!")
            logger.info(f"✅ Successfully sent {total_synced:,} points to production")
            logger.info(
                f"📄 Processed {page_num - 1} pages of {page_size:,} records each"
            )
            logger.info(f"⏱️  Duration: {duration}")

            return True

        except Exception as e:
            logger.error(f"❌ Error in paginated sync: {e}")
            return False

    def sync_data(
        self,
        days_back: int = 7,
        use_inventory: bool = False,
        dry_run: bool = False,
        specific_sensors: Optional[List[str]] = None,
    ) -> bool:
        """Legacy method: Full sync operation (both stages)"""

        logger.info("🚀 Full two-stage sync: Aquarius → Local → Production")

        # Stage 1: Aquarius to Local
        stage1_success = self.sync_aquarius_to_local(
            days_back=days_back,
            use_inventory=use_inventory,
            dry_run=dry_run,
            specific_sensors=specific_sensors,
        )

        if not stage1_success or dry_run:
            return stage1_success

        # Stage 2: Local to Production
        stage2_success = self.sync_local_to_production(dry_run=dry_run)

        return stage1_success and stage2_success


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Ecosense Data Sync - Two-Stage Architecture (Aquarius → Local → Production)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full two-stage sync (default)
  python ecosense_sync.py                      # Sync last 7 days (both stages)
  python ecosense_sync.py --days 30           # Sync last 30 days (both stages)
  
  # Stage-specific operations
  python ecosense_sync.py --local-only        # Stage 1: Aquarius → Local DB only
  python ecosense_sync.py --production-only   # Stage 2: Local DB → Production only
  
  # Testing and configuration
  python ecosense_sync.py --test              # Test all connections
  python ecosense_sync.py --dry-run           # Show what would be synced
  python ecosense_sync.py --use-inventory     # Use smart filtering
  python ecosense_sync.py --stats             # Show database statistics
  
  # Advanced options
  python ecosense_sync.py --batch-size 250    # Smaller batches for rate limiting
  python ecosense_sync.py --sensors sensor1 sensor2  # Specific sensors only
        """,
    )

    # Operation modes
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--test", action="store_true", help="Test connections only")
    mode_group.add_argument(
        "--local-only",
        action="store_true",
        help="Stage 1 only: Sync Aquarius to local database",
    )
    mode_group.add_argument(
        "--production-only",
        action="store_true",
        help="Stage 2 only: Sync local database to production",
    )
    mode_group.add_argument(
        "--stats", action="store_true", help="Show database statistics"
    )

    # Sync configuration
    parser.add_argument(
        "--days", type=int, default=7, help="Days of data to sync (default: 7)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Batch size for production sync (default: 500)",
    )
    parser.add_argument(
        "--use-inventory",
        action="store_true",
        help="Enable smart filtering using local DB inventory",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be synced without actually syncing",
    )
    parser.add_argument("--sensors", nargs="+", help="Specific sensor IDs to sync")
    parser.add_argument(
        "--all-data",
        action="store_true",
        help="Sync ALL historical data (for --production-only mode)",
    )

    args = parser.parse_args()

    # Validate required environment variables
    required_vars = ["AQUARIUS_HOSTNAME", "AQUARIUS_USERNAME", "AQUARIUS_PASSWORD"]

    # Production variables only needed for production sync
    if not args.local_only and not args.stats:
        required_vars.extend(["REMOTE_DB_HOST", "PG_PROXY_TOKEN"])

    # Local database variables needed for most operations
    if not args.production_only:
        required_vars.extend(["LOCAL_DB_HOST", "LOCAL_DB_USER", "LOCAL_DB_PASSWORD"])

    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        logger.error(f"❌ Missing required environment variables: {missing_vars}")
        sys.exit(1)

    # Create sync instance
    sync = EcosenseSync()

    # Handle test mode
    if args.test:
        success = sync.test_connections()
        if success:
            logger.info("🎉 All connections successful!")
        sys.exit(0 if success else 1)

    # Handle stats mode
    if args.stats:
        logger.info("📊 Database Statistics:")

        # Local database stats
        try:
            local_stats = sync.local_db.get_local_stats()
            if local_stats.get("stats"):
                logger.info("\n🗄️  Local Database:")
                for stat in local_stats["stats"]:
                    logger.info(
                        f"  {stat['parameter']}: {stat['total_points']:,} points, "
                        f"{stat['unique_series']} series, "
                        f"{stat['earliest']} to {stat['latest']}"
                    )
            else:
                logger.info("🗄️  Local Database: No data")
        except Exception as e:
            logger.error(f"❌ Could not get local stats: {e}")

        # Production database stats (if accessible)
        if not args.local_only:
            try:
                prod_stats = sync.production.get_stats()
                if prod_stats.get("data"):
                    logger.info("\n🌐 Production Database:")
                    for stat in prod_stats["data"]:
                        logger.info(
                            f"  {stat['parameter']}: {stat['total_points']:,} points, "
                            f"{stat['unique_series']} series, "
                            f"{stat['earliest']} to {stat['latest']}"
                        )
                else:
                    logger.info("🌐 Production Database: No data or inaccessible")
            except Exception as e:
                logger.warning(f"⚠️  Could not get production stats: {e}")

        sys.exit(0)

    # Handle different sync modes
    success = False

    if args.local_only:
        # Stage 1 only: Aquarius → Local
        success = sync.sync_aquarius_to_local(
            days_back=args.days,
            use_inventory=args.use_inventory,
            dry_run=args.dry_run,
            specific_sensors=args.sensors,
        )

    elif args.production_only:
        # Stage 2 only: Local → Production
        days_back = (
            None if args.all_data else 7
        )  # Default to recent data unless --all-data specified
        success = sync.sync_local_to_production(
            batch_size=args.batch_size, dry_run=args.dry_run, days_back=days_back
        )

    else:
        # Full sync (both stages) - backward compatible
        success = sync.sync_data(
            days_back=args.days,
            use_inventory=args.use_inventory,
            dry_run=args.dry_run,
            specific_sensors=args.sensors,
        )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
