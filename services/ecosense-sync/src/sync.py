import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import psycopg2
import requests
from psycopg2.extras import Json, RealDictCursor, execute_values

from .config import settings
from .database import get_db_connection

logger = logging.getLogger(__name__)


class AquariusClient:
    def __init__(self):
        self.hostname = settings.AQUARIUS_HOSTNAME.rstrip("/")
        self.username = settings.AQUARIUS_USERNAME
        self.password = settings.AQUARIUS_PASSWORD
        self.session = requests.Session()
        self.token = None

        if "/AQUARIUS" in self.hostname:
            self.base_url = f"{self.hostname}/Publish/v2"
        else:
            self.base_url = f"{self.hostname}/AQUARIUS/Publish/v2"

    def connect(self) -> bool:
        try:
            auth_url = f"{self.base_url}/session"
            response = self.session.post(
                auth_url,
                json={"Username": self.username, "EncryptedPassword": self.password},
                timeout=30,
            )
            if response.status_code == 200:
                self.token = response.text.strip('\\"')
                self.session.headers.update({"X-Authentication-Token": self.token})
                return True
            return False
        except Exception as e:
            logger.error(f"Aquarius connection error: {e}")
            return False

    def disconnect(self):
        if self.token:
            try:
                self.session.delete(f"{self.base_url}/session")
            except Exception:
                pass

    def get_time_series_descriptions(self) -> List[Dict]:
        try:
            response = self.session.get(
                f"{self.base_url}/GetTimeSeriesDescriptionList", timeout=60
            )
            if response.status_code == 200:
                return response.json().get("TimeSeriesDescriptions", [])
            return []
        except Exception as e:
            logger.error(f"Error fetching descriptions: {e}")
            return []

    def get_data(
        self, unique_id: str, start_time: datetime, end_time: datetime
    ) -> List[Dict]:
        try:
            start_str = start_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
            end_str = end_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

            params = {
                "TimeSeriesUniqueId": unique_id,
                "QueryFrom": start_str,
                "QueryTo": end_str,
            }

            response = self.session.get(
                f"{self.base_url}/GetTimeSeriesCorrectedData", params=params, timeout=60
            )

            if response.status_code == 200:
                return response.json().get("Points", [])
            return []
        except Exception as e:
            logger.error(f"Error fetching data for {unique_id}: {e}")
            return []


class EcosenseSync:
    def __init__(self):
        self.client = AquariusClient()

        # Parameter to SensorType mapping
        self.param_mapping = {
            "Sapflow": "Sap_Flow",
            "StemRadialVar_Volt": "Stem_Radial_Variation",
            "BarPressure": "Barometric_Pressure",
            "SoilMoisture": "Soil_Moisture",
            "SoilTemp": "Soil_Temperature",
            # Add others if needed
        }

    def _get_sensor_types(self, conn) -> Dict[str, int]:
        with conn.cursor() as cur:
            cur.execute("SELECT SensorTypeName, SensorTypeID FROM sensor.SensorTypes")
            return {row[0]: row[1] for row in cur.fetchall()}

    def _get_locations(self, conn) -> Dict[str, int]:
        with conn.cursor() as cur:
            cur.execute("SELECT LocationName, LocationID FROM shared.Locations")
            return {row[0]: row[1] for row in cur.fetchall()}

    def _get_or_create_location(self, conn, location_name: str) -> int:
        if not location_name:
            location_name = "Unknown"

        # Simple cache could be added here
        with conn.cursor() as cur:
            cur.execute(
                "SELECT LocationID FROM shared.Locations WHERE LocationName = %s",
                (location_name,),
            )
            res = cur.fetchone()
            if res:
                return res[0]

            # Create new location if not exists (default values)
            # Using a default point (0,0) for now
            cur.execute(
                """
                INSERT INTO shared.Locations (LocationName, CenterPoint)
                VALUES (%s, ST_SetSRID(ST_MakePoint(0, 0), 4326))
                RETURNING LocationID
            """,
                (location_name,),
            )
            result = cur.fetchone()
            if result:
                return result[0]
            raise Exception("Failed to create location")

    def sync_metadata(self):
        logger.info("Starting metadata sync...")
        if not self.client.connect():
            logger.error("Could not connect to Aquarius")
            return

        try:
            conn = get_db_connection()
            sensor_types = self._get_sensor_types(conn)

            descriptions = self.client.get_time_series_descriptions()
            logger.info(f"Fetched {len(descriptions)} time series descriptions")

            # Filter for Ecosense and known parameters
            ecosense_ts = [
                ts
                for ts in descriptions
                if str(ts.get("LocationIdentifier", "")).startswith("Ecosense_")
                and ts.get("Parameter") in self.param_mapping
            ]

            logger.info(f"Filtered to {len(ecosense_ts)} relevant sensors")

            for ts in ecosense_ts:
                param = str(ts.get("Parameter"))
                mapped_type = self.param_mapping.get(param)
                if not mapped_type or mapped_type not in sensor_types:
                    continue

                type_id = sensor_types[mapped_type]
                location_name = str(ts.get("LocationIdentifier"))
                label = ts.get("Label")
                unique_id = ts.get("UniqueId")
                unit = ts.get("Unit")

                location_id = self._get_or_create_location(conn, location_name)

                # Upsert Sensor
                # We use ExternalID to identify unique sensors
                # Position defaults to (0,0) if not known
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO sensor.Sensors (
                            LocationID, SensorTypeID, SensorModel, SerialNumber, 
                            Position, SamplingInterval_seconds, Unit, 
                            ExternalID, ExternalMetadata, IsActive
                        ) VALUES (
                            %s, %s, %s, %s, 
                            ST_SetSRID(ST_MakePoint(0, 0), 4326), 900, %s,
                            %s, %s, TRUE
                        )
                        ON CONFLICT (ExternalID) DO UPDATE SET
                            LocationID = EXCLUDED.LocationID,
                            SensorTypeID = EXCLUDED.SensorTypeID,
                            Unit = EXCLUDED.Unit,
                            ExternalMetadata = EXCLUDED.ExternalMetadata,
                            UpdatedAt = NOW()
                        RETURNING SensorID
                    """,
                        (
                            location_id,
                            type_id,
                            "Ecosense Node",
                            label,
                            unit,
                            unique_id,
                            Json(ts),
                        ),
                    )

            conn.commit()
            conn.close()
            logger.info("Metadata sync completed")

        except Exception as e:
            logger.error(f"Metadata sync failed: {e}")
        finally:
            self.client.disconnect()

    def sync_readings(
        self, days_back: int = 7, sensor_external_ids: Optional[List[str]] = None
    ):
        logger.info(f"Starting readings sync (days_back={days_back})...")
        if not self.client.connect():
            return

        try:
            conn = get_db_connection()

            # Get sensors to sync
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = "SELECT SensorID, ExternalID, SensorTypeID FROM sensor.Sensors WHERE ExternalID IS NOT NULL AND IsActive = TRUE"
                if sensor_external_ids:
                    query += " AND ExternalID = ANY(%s)"
                    cur.execute(query, (sensor_external_ids,))
                else:
                    cur.execute(query)
                sensors = cur.fetchall()

            logger.info(f"Syncing readings for {len(sensors)} sensors")

            end_time = datetime.now()
            start_time = end_time - timedelta(days=days_back)

            total_points = 0

            for i, sensor in enumerate(sensors):
                unique_id = sensor["externalid"]
                sensor_id = sensor["sensorid"]

                points = self.client.get_data(unique_id, start_time, end_time)
                if not points:
                    continue

                # Prepare data for bulk insert
                values = []
                for p in points:
                    if (
                        "Value" in p
                        and "Numeric" in p["Value"]
                        and p["Value"]["Numeric"] is not None
                    ):
                        ts = p["Timestamp"].replace(
                            "Z", "+00:00"
                        )  # Simple fix, ideally use dateutil
                        val = float(p["Value"]["Numeric"])
                        # Quality mapping could be added here
                        quality = "good"
                        values.append((sensor_id, ts, val, quality))

                if values:
                    with conn.cursor() as cur:
                        execute_values(
                            cur,
                            """
                            INSERT INTO sensor.SensorReadings (SensorID, Timestamp, Value, Quality)
                            VALUES %s
                            ON CONFLICT DO NOTHING
                        """,
                            values,
                        )
                    conn.commit()
                    total_points += len(values)

                if i % 10 == 0:
                    logger.info(f"Processed {i}/{len(sensors)} sensors")

            logger.info(f"Readings sync completed. Inserted {total_points} points.")
            conn.close()

        except Exception as e:
            logger.error(f"Readings sync failed: {e}")
        finally:
            self.client.disconnect()

    def sync_all(self, days_back: int = 7):
        self.sync_metadata()
        self.sync_readings(days_back=days_back)
