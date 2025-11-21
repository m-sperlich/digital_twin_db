#!/usr/bin/env python3
"""
Ecosense Focused Data Sync Script
Based on official Aquarius Python integration patterns and R Shiny app requirements.

This script only syncs the specific parameters and locations used by the R Shiny app:
- Parameters: Sapflow, StemRadialVar_Volt, BarPressure, SoilMoisture, SoilTemp
- Locations: Only Ecosense_* locations
- Data: Last 1000 days (matching R app)
"""

import logging
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

import psycopg2
import requests
import schedule
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("ecosense_focused_sync.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


@dataclass
class EcosenseSensor:
    """Represents a sensor that the R Shiny app expects"""

    label: str
    location_identifier: str
    parameter: str
    parameter_unit: str
    timeseries_identifier: str  # parameter.label@location_identifier
    unique_id: Optional[str] = None


class OfficialAquariusClient:
    """Official Aquarius Python client based on GitHub examples"""

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

    def connect(self):
        """Connect using official timeseries_client patterns"""
        try:
            auth_url = f"{self.base_url}/session"

            logger.info(f"Connecting to AQUARIUS at: {auth_url}")

            response = self.session.post(
                auth_url,
                json={
                    "Username": self.username,
                    "EncryptedPassword": self.password,  # Official client uses EncryptedPassword
                },
                timeout=30,
            )

            if response.status_code == 200:
                self.token = response.text.strip('\\"')  # Remove quotes if present
                self.session.headers.update({"X-Authentication-Token": self.token})
                logger.info("Successfully connected to AQUARIUS")
                return True
            else:
                logger.error(
                    f"Connection failed: {response.status_code} - {response.text}"
                )
                return False

        except Exception as e:
            logger.error(f"Connection error: {e}")
            return False

    def disconnect(self):
        """Destroy the authenticated session"""
        try:
            if self.token:
                self.session.delete(f"{self.base_url}/session")
                logger.info("Disconnected from AQUARIUS")
        except Exception as e:
            logger.warning(f"Disconnect warning: {e}")

    def get_ecosense_time_series_descriptions(self) -> List[dict]:
        """Get all time series descriptions for Ecosense locations"""
        try:
            # Get all time series descriptions (not just published)
            response = self.session.get(
                f"{self.base_url}/GetTimeSeriesDescriptionList", timeout=30
            )

            if response.status_code == 200:
                all_series = response.json().get("TimeSeriesDescriptions", [])

                # Filter for Ecosense locations only
                ecosense_series = [
                    ts
                    for ts in all_series
                    if ts.get("LocationIdentifier", "").startswith("Ecosense_")
                ]

                logger.info(
                    f"Found {len(ecosense_series)} Ecosense time series out of {len(all_series)} total"
                )
                return ecosense_series

            else:
                logger.error(
                    f"Failed to get time series descriptions: {response.status_code}"
                )
                return []

        except Exception as e:
            logger.error(f"Error getting time series descriptions: {e}")
            return []

    def get_ecosense_sensors_for_r_app(self, db_manager=None) -> List[EcosenseSensor]:
        """Get only the sensors needed by the R Shiny app - filtered by inventory links"""

        # Parameters that the R Shiny app looks for
        TARGET_PARAMETERS = {
            "Sapflow",
            "StemRadialVar_Volt",
            "BarPressure",
            "SoilMoisture",
            "SoilTemp",
        }

        # Get linked sensor names from inventory if database connection available
        linked_sensor_names = set()
        if db_manager and db_manager.local_conn:
            try:
                with db_manager.local_conn.cursor() as cursor:
                    cursor.execute(
                        "SELECT DISTINCT aquariusname FROM ecosense.link_sensors_trees_inventory WHERE aquariusname IS NOT NULL"
                    )
                    linked_names = cursor.fetchall()
                    linked_sensor_names = {name[0] for name in linked_names if name[0]}
                    logger.info(
                        f"Found {len(linked_sensor_names)} sensor names linked to trees in inventory"
                    )
            except Exception as e:
                logger.warning(f"Could not get linked sensor names from inventory: {e}")

        time_series = self.get_ecosense_time_series_descriptions()
        sensors = []
        filtered_count = 0

        for ts in time_series:
            parameter = ts.get("Parameter", "")
            location_id = ts.get("LocationIdentifier", "")
            label = ts.get(
                "Label",
                (
                    ts.get("Identifier", "").split(".")[1]
                    if "." in ts.get("Identifier", "")
                    else ""
                ),
            )
            unique_id = ts.get("UniqueId", "")
            unit = ts.get("Unit", "")

            # Only include parameters that the R app uses
            if parameter in TARGET_PARAMETERS and location_id.startswith("Ecosense_"):

                # If we have inventory data, filter by sensors that are actually linked to trees
                if linked_sensor_names:
                    # Check if this sensor label matches any linked sensor name (using ILIKE logic)
                    label_matches = any(
                        label.lower().startswith(linked_name.lower())
                        for linked_name in linked_sensor_names
                    )
                    if not label_matches:
                        filtered_count += 1
                        continue

                # Construct the timeseries identifier like the R app does
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

        if linked_sensor_names:
            logger.info(f"Filtered out {filtered_count} sensors not linked to trees")
        logger.info(f"Found {len(sensors)} Ecosense sensors needed by R app")

        # Log summary by parameter
        by_param = {}
        for sensor in sensors:
            by_param.setdefault(sensor.parameter, 0)
            by_param[sensor.parameter] += 1

        for param, count in by_param.items():
            logger.info(f"  {param}: {count} sensors")

        return sensors

    def get_time_series_corrected_data(
        self, unique_id: str, query_from: datetime, query_to: datetime
    ) -> Optional[dict]:
        """Get time series data using official client method"""
        try:
            # Format timestamps as ISO 8601 strings (official pattern)
            start_str = query_from.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
            end_str = query_to.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

            params = {
                "TimeSeriesUniqueId": unique_id,
                "QueryFrom": start_str,
                "QueryTo": end_str,
            }

            response = self.session.get(
                f"{self.base_url}/GetTimeSeriesCorrectedData", params=params, timeout=60
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(
                    f"Failed to get data for {unique_id}: {response.status_code} - {response.text}"
                )
                return None

        except Exception as e:
            logger.error(f"Error getting time series data for {unique_id}: {e}")
            return None


class DatabaseManager:
    """Manages database operations matching R app schema"""

    def __init__(self):
        self.local_conn: Optional[psycopg2.extensions.connection] = None
        self.remote_base_url = f"https://{os.getenv('REMOTE_DB_HOST')}/api/db"
        self.auth_token = os.getenv("PG_PROXY_TOKEN")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.auth_token}",
                "Content-Type": "application/json",
            }
        )

    def connect_local(self) -> bool:
        """Connect to local PostgreSQL database"""
        try:
            self.local_conn = psycopg2.connect(
                host=os.getenv("LOCAL_DB_HOST", "localhost"),
                port=int(os.getenv("LOCAL_DB_PORT", "5432")),
                database=os.getenv("LOCAL_DB_NAME", "sensors"),
                user=os.getenv("LOCAL_DB_USER", "postgres"),
                password=os.getenv("LOCAL_DB_PASSWORD", "postgres"),
            )
            logger.info("Connected to local database")
            return True
        except Exception as e:
            logger.error(f"Local database connection failed: {e}")
            return False

    def test_remote_connection(self) -> bool:
        """Test connection to remote HTTP proxy"""
        try:
            response = self.session.get(f"{self.remote_base_url}/health", timeout=10)
            if response.status_code == 200:
                logger.info("Connected to remote database via HTTP proxy")
                return True
            else:
                logger.error(
                    f"Remote HTTP proxy connection failed: {response.status_code}"
                )
                return False
        except Exception as e:
            logger.error(f"Remote HTTP proxy connection failed: {e}")
            return False

    def upsert_sensor_metadata(self, sensor: EcosenseSensor) -> bool:
        """Upsert sensor metadata to local database matching R app schema"""
        if not self.local_conn:
            logger.error("No local database connection")
            return False

        try:
            with self.local_conn.cursor() as cursor:
                # Check if record exists first
                cursor.execute(
                    """
                    SELECT COUNT(*) FROM ecosense.ecosense_sensors 
                    WHERE label = %s AND locationidentifier = %s AND parameter = %s
                """,
                    (sensor.label, sensor.location_identifier, sensor.parameter),
                )
                result = cursor.fetchone()
                exists = result and result[0] > 0

                if exists:
                    # Update existing record
                    cursor.execute(
                        """
                        UPDATE ecosense.ecosense_sensors 
                        SET parameterunit = %s
                        WHERE label = %s AND locationidentifier = %s AND parameter = %s
                    """,
                        (
                            sensor.parameter_unit,
                            sensor.label,
                            sensor.location_identifier,
                            sensor.parameter,
                        ),
                    )
                else:
                    # Insert new record
                    cursor.execute(
                        """
                        INSERT INTO ecosense.ecosense_sensors (
                            label, locationidentifier, parameter, parameterunit
                        ) VALUES (%s, %s, %s, %s)
                    """,
                        (
                            sensor.label,
                            sensor.location_identifier,
                            sensor.parameter,
                            sensor.parameter_unit,
                        ),
                    )

            self.local_conn.commit()
            return True

        except Exception as e:
            logger.error(f"Error upserting sensor metadata: {e}")
            self.local_conn.rollback()
            return False

    def insert_timeseries_data_remote(
        self, data_points: List[Tuple], batch_size: int = 500, max_retries: int = 3
    ) -> bool:
        """Insert time series data points via HTTP proxy in batches with rate limiting"""
        if not data_points:
            return False

        try:
            total_points = len(data_points)
            logger.info(
                f"Inserting {total_points} data points in batches of {batch_size}"
            )

            # Process in batches
            for batch_start in range(0, total_points, batch_size):
                batch_end = min(batch_start + batch_size, total_points)
                batch_points = data_points[batch_start:batch_end]

                formatted_data = []
                for point in batch_points:
                    formatted_data.append(
                        {
                            "timeseries_id": point[0],
                            "timestamp": point[1].isoformat(),
                            "value": float(point[2]),
                            "parameter": point[3],
                            "sensor_label": point[4],
                            "location_identifier": point[5],
                        }
                    )

                payload = {"data_points": formatted_data}

                # Retry with exponential backoff for rate limiting
                for retry in range(max_retries):
                    try:
                        response = self.session.post(
                            f"{self.remote_base_url}/timeseries/bulk-insert",
                            json=payload,
                            timeout=120,  # Increased timeout
                        )

                        if response.status_code == 200:
                            result = response.json()
                            if result["success"]:
                                logger.info(
                                    f"Batch {batch_start//batch_size + 1}/{(total_points + batch_size - 1)//batch_size}: "
                                    f"Successfully inserted/updated {result['inserted_count']} data points"
                                )
                                break  # Success, exit retry loop
                            else:
                                logger.error(
                                    f"HTTP proxy insertion failed for batch: {result}"
                                )
                                return False
                        elif response.status_code == 429:  # Rate limit
                            wait_time = (
                                2**retry
                            ) * 2  # Exponential backoff: 2, 4, 8 seconds
                            logger.warning(
                                f"Rate limit hit, waiting {wait_time}s before retry {retry+1}/{max_retries}"
                            )
                            time.sleep(wait_time)
                            continue
                        else:
                            logger.error(
                                f"HTTP proxy request failed for batch: {response.status_code} - {response.text[:200]}"
                            )
                            if retry == max_retries - 1:  # Last retry
                                return False
                            time.sleep((2**retry) * 1)  # Wait before retry
                            continue

                    except Exception as e:
                        logger.error(f"Error in batch request (retry {retry+1}): {e}")
                        if retry == max_retries - 1:  # Last retry
                            return False
                        time.sleep((2**retry) * 1)
                        continue
                else:
                    # All retries failed
                    logger.error(f"Failed to insert batch after {max_retries} retries")
                    return False

                # Longer delay between successful batches to avoid rate limits
                time.sleep(1.0)

            logger.info(
                f"Successfully inserted all {total_points} data points in {(total_points + batch_size - 1)//batch_size} batches"
            )
            return True

        except Exception as e:
            logger.error(f"Error inserting time series data via HTTP proxy: {e}")
            return False

    def get_last_sync_time_remote(
        self, timeseries_id: str, max_retries: int = 3
    ) -> Optional[datetime]:
        """Get the last sync timestamp for a time series via HTTP proxy with retry logic"""
        for retry in range(max_retries):
            try:
                response = self.session.get(
                    f"{self.remote_base_url}/timeseries/last-sync/{timeseries_id}",
                    timeout=15,
                )

                if response.status_code == 200:
                    result = response.json()
                    if result["success"] and result["last_sync"]:
                        return datetime.fromisoformat(
                            result["last_sync"].replace("Z", "+00:00")
                        )
                    else:
                        # Default to 7 days back for initial sync (much smaller window)
                        return datetime.now() - timedelta(days=7)
                elif response.status_code == 429:  # Rate limit
                    wait_time = (2**retry) * 1  # Exponential backoff
                    logger.warning(
                        f"Rate limit getting last sync time, waiting {wait_time}s"
                    )
                    time.sleep(wait_time)
                    continue
                else:
                    logger.warning(
                        f"Failed to get last sync time for {timeseries_id}: {response.status_code}"
                    )
                    return datetime.now() - timedelta(days=7)  # Smaller default window

            except Exception as e:
                if retry == max_retries - 1:
                    logger.error(
                        f"Error getting last sync time for {timeseries_id}: {e}"
                    )
                else:
                    logger.warning(
                        f"Retry {retry+1} for last sync time {timeseries_id}: {e}"
                    )
                    time.sleep((2**retry) * 1)

        # Fallback to 7 days (much smaller window)
        return datetime.now() - timedelta(days=7)

    def close_connections(self):
        """Close database connections"""
        if self.local_conn:
            self.local_conn.close()
        self.session.close()


class EcosenseDataSyncer:
    """Main syncer focused on R Shiny app requirements"""

    def __init__(self):
        self.aquarius = OfficialAquariusClient(
            hostname=os.getenv("AQUARIUS_HOSTNAME", ""),
            username=os.getenv("AQUARIUS_USERNAME", ""),
            password=os.getenv("AQUARIUS_PASSWORD", ""),
        )
        self.db = DatabaseManager()

    def sync_sensor_data(self, sensor: EcosenseSensor, days_back: int = 7) -> bool:
        """Sync data for a single sensor (with smaller default window)"""

        if not sensor.unique_id:
            logger.warning(f"No unique ID for sensor {sensor.timeseries_identifier}")
            return False

        # Get last sync time or default to smaller window (7 days max for initial requests)
        last_sync = self.db.get_last_sync_time_remote(sensor.timeseries_identifier)
        if not last_sync:
            # For initial sync, use much smaller window to avoid overwhelming the system
            effective_days_back = min(days_back, 7)
            start_time = datetime.now() - timedelta(days=effective_days_back)
        else:
            start_time = last_sync - timedelta(hours=1)  # Small overlap

        end_time = datetime.now()

        logger.info(
            f"Syncing {sensor.parameter} at {sensor.location_identifier} from {start_time} to {end_time}"
        )

        # Fetch data from Aquarius
        ts_data = self.aquarius.get_time_series_corrected_data(
            sensor.unique_id, start_time, end_time
        )

        if not ts_data or "Points" not in ts_data:
            logger.warning(f"No data received for {sensor.timeseries_identifier}")
            return False

        points = ts_data.get("Points", [])
        if not points:
            logger.info(f"No new data points for {sensor.timeseries_identifier}")
            return True

        logger.info(
            f"Retrieved {len(points)} data points for {sensor.timeseries_identifier}"
        )

        # Convert to database format (matching R app expectations)
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
                    (
                        sensor.timeseries_identifier,  # Use the same format as R app
                        timestamp,
                        value,
                        sensor.parameter,
                        sensor.label,
                        sensor.location_identifier,
                    )
                )

        if data_points:
            # Use smaller batch size for better HTTP proxy handling
            success = self.db.insert_timeseries_data_remote(data_points, batch_size=200)
            if success:
                logger.info(
                    f"Synced {len(data_points)} points for {sensor.timeseries_identifier}"
                )
            return success
        else:
            logger.info(f"No valid data points for {sensor.timeseries_identifier}")
            return True

    def full_sync(self, days_back: int = 1000) -> bool:
        """Perform full sync for all sensors needed by R app"""
        logger.info(f"Starting Ecosense-focused sync (last {days_back} days)")

        # Connect to Aquarius
        if not self.aquarius.connect():
            logger.error("Failed to connect to AQUARIUS")
            return False

        try:
            # Connect to databases
            if not self.db.connect_local():
                logger.error("Failed to connect to local database")
                return False

            if not self.db.test_remote_connection():
                logger.error("Failed to connect to remote HTTP proxy")
                return False

            # Get sensors needed by R app (filtered by inventory links)
            sensors = self.aquarius.get_ecosense_sensors_for_r_app(self.db)
            if not sensors:
                logger.error("No Ecosense sensors found for R app parameters")
                return False

            # Sync metadata first
            logger.info("Syncing sensor metadata to local database...")
            metadata_success = 0
            for sensor in sensors:
                if self.db.upsert_sensor_metadata(sensor):
                    metadata_success += 1

            logger.info(
                f"Synced metadata for {metadata_success}/{len(sensors)} sensors"
            )

            # Sync time series data
            logger.info("Syncing time series data...")
            success_count = 0

            for sensor in sensors:
                try:
                    if self.sync_sensor_data(sensor, days_back):
                        success_count += 1
                    else:
                        logger.warning(f"Failed to sync {sensor.timeseries_identifier}")

                    # Longer delay between sensors to avoid rate limits
                    time.sleep(2.0)

                except Exception as e:
                    logger.error(f"Error syncing {sensor.timeseries_identifier}: {e}")

            logger.info(
                f"Data sync completed: {success_count}/{len(sensors)} sensors successful"
            )
            return success_count > 0

        finally:
            # Always disconnect
            self.aquarius.disconnect()
            self.db.close_connections()


def main():
    """Main function"""
    syncer = EcosenseDataSyncer()

    # Validate required environment variables
    required_vars = [
        "AQUARIUS_HOSTNAME",
        "AQUARIUS_USERNAME",
        "AQUARIUS_PASSWORD",
        "REMOTE_DB_HOST",
        "PG_PROXY_TOKEN",
        "LOCAL_DB_HOST",
        "LOCAL_DB_USER",
        "LOCAL_DB_PASSWORD",
    ]

    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        logger.error(f"Missing required environment variables: {missing_vars}")
        sys.exit(1)

    # Handle command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "--schedule":
            logger.info("Starting scheduled Ecosense data sync")

            # Run daily sync for last 7 days
            schedule.every().day.at("02:00").do(lambda: syncer.full_sync(days_back=7))

            # Initial full sync for 1000 days
            syncer.full_sync(days_back=1000)

            while True:
                schedule.run_pending()
                time.sleep(60)

        elif sys.argv[1] == "--backfill":
            days = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
            logger.info(f"Starting Ecosense backfill for last {days} days")
            syncer.full_sync(days_back=days)

        elif sys.argv[1] == "--test":
            logger.info("Testing Ecosense sensor discovery")
            if syncer.aquarius.connect():
                # Connect to database for inventory filtering
                syncer.db.connect_local()
                sensors = syncer.aquarius.get_ecosense_sensors_for_r_app(syncer.db)
                logger.info(f"Found {len(sensors)} sensors for R app")
                for sensor in sensors[:5]:  # Show first 5
                    logger.info(f"  {sensor.timeseries_identifier}")
                syncer.aquarius.disconnect()
                syncer.db.close_connections()
            else:
                logger.error("Failed to connect to Aquarius")

        else:
            logger.error(
                "Usage: python ecosense_focused_sync.py [--schedule | --backfill [days] | --test]"
            )
            sys.exit(1)
    else:
        # Default: sync last 1000 days (matching R app)
        syncer.full_sync(days_back=1000)


if __name__ == "__main__":
    main()
