#!/usr/bin/env python3
"""
Ecosense Production Sync Client
Syncs data from local database or Aquarius directly to production server.
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import argparse

import psycopg2
import psycopg2.extras
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("production_sync.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


class ProductionSyncClient:
    """Client for syncing data to production server via pg-http-proxy"""

    def __init__(self):
        self.remote_host = os.getenv('REMOTE_DB_HOST', 'dt.unr.uni-freiburg.de')
        self.remote_port = os.getenv('REMOTE_DB_PORT', '443')
        self.remote_protocol = os.getenv('REMOTE_DB_PROTOCOL', 'https')
        self.api_token = os.getenv('PG_PROXY_TOKEN')

        if not self.api_token:
            raise ValueError("PG_PROXY_TOKEN environment variable is required")

        self.base_url = f"{self.remote_protocol}://{self.remote_host}:{self.remote_port}/api/db"
        if self.remote_port == '443' and self.remote_protocol == 'https':
            self.base_url = f"{self.remote_protocol}://{self.remote_host}/api/db"

        self.headers = {
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json'
        }

        logger.info(f"Initialized sync client for {self.base_url}")

    def test_connection(self) -> bool:
        """Test connection to production server"""
        try:
            response = requests.get(f"{self.base_url}/health", headers=self.headers, timeout=30)
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ Production server connection successful: {data}")
                return True
            else:
                logger.error(f"❌ Health check failed: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            logger.error(f"❌ Connection test failed: {e}")
            return False

    def get_production_stats(self) -> Dict[str, Any]:
        """Get statistics from production database"""
        try:
            response = requests.get(f"{self.base_url}/timeseries/stats", headers=self.headers, timeout=30)
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get stats: {response.status_code} - {response.text}")
                return {}
        except Exception as e:
            logger.error(f"Error getting production stats: {e}")
            return {}

    def get_sensors_metadata(self) -> List[Dict[str, Any]]:
        """Get sensor metadata from production"""
        try:
            response = requests.get(f"{self.base_url}/sensors/metadata", headers=self.headers, timeout=30)
            if response.status_code == 200:
                data = response.json()
                return data.get('data', [])
            else:
                logger.error(f"Failed to get sensors: {response.status_code} - {response.text}")
                return []
        except Exception as e:
            logger.error(f"Error getting sensors metadata: {e}")
            return []

    def bulk_insert_data(self, data_points: List[Dict[str, Any]]) -> bool:
        """Send data points to production server"""
        if not data_points:
            logger.warning("No data points to insert")
            return True

        try:
            # Split into chunks to respect API limits
            chunk_size = 1000
            total_sent = 0

            for i in range(0, len(data_points), chunk_size):
                chunk = data_points[i:i + chunk_size]

                payload = {
                    "data_points": chunk
                }

                response = requests.post(
                    f"{self.base_url}/timeseries/bulk-insert",
                    headers=self.headers,
                    json=payload,
                    timeout=60
                )

                if response.status_code == 200:
                    result = response.json()
                    total_sent += result.get('inserted_count', len(chunk))
                    logger.info(f"✅ Sent chunk {i//chunk_size + 1}: {result.get('inserted_count', len(chunk))} points")
                else:
                    logger.error(f"❌ Failed to send chunk: {response.status_code} - {response.text}")
                    return False

                # Rate limiting - small delay between chunks
                if i + chunk_size < len(data_points):
                    time.sleep(1)

            logger.info(f"🎉 Successfully sent {total_sent} data points to production")
            return True

        except Exception as e:
            logger.error(f"Error sending data to production: {e}")
            return False


class LocalDataExtractor:
    """Extracts data from local database for sync"""

    def __init__(self):
        self.local_db_config = {
            'host': os.getenv('LOCAL_DB_HOST', 'localhost'),
            'port': int(os.getenv('LOCAL_DB_PORT', '5432')),
            'database': os.getenv('LOCAL_DB_NAME', 'sensors'),
            'user': os.getenv('LOCAL_DB_USER', 'postgres'),
            'password': os.getenv('LOCAL_DB_PASSWORD', 'postgres')
        }

    def get_connection(self):
        """Get local database connection"""
        return psycopg2.connect(**self.local_db_config)

    def get_timeseries_data(self, days_back: int = 7, specific_sensors: List[str] = None) -> List[Dict[str, Any]]:
        """Extract timeseries data from local database"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            # Build query with optional sensor filtering
            where_clause = "WHERE td.timestamp >= %s"
            params = [datetime.now() - timedelta(days=days_back)]

            if specific_sensors:
                placeholders = ','.join(['%s'] * len(specific_sensors))
                where_clause += f" AND td.timeseries_id IN ({placeholders})"
                params.extend(specific_sensors)

            query = f"""
                SELECT
                    td.timeseries_id,
                    td.timestamp,
                    td.value,
                    td.parameter,
                    td.sensor_label,
                    td.location_identifier
                FROM ecosense.timeseries_data td
                {where_clause}
                ORDER BY td.timeseries_id, td.timestamp
            """

            cursor.execute(query, params)
            results = cursor.fetchall()

            cursor.close()
            conn.close()

            # Convert to format expected by API
            data_points = []
            for row in results:
                data_points.append({
                    "timeseries_id": row['timeseries_id'],
                    "timestamp": row['timestamp'].isoformat(),
                    "value": float(row['value']),
                    "parameter": row['parameter'],
                    "sensor_label": row['sensor_label'],
                    "location_identifier": row['location_identifier']
                })

            logger.info(f"Extracted {len(data_points)} data points from local database")
            return data_points

        except Exception as e:
            logger.error(f"Error extracting data from local database: {e}")
            return []


def main():
    """Main sync function"""
    parser = argparse.ArgumentParser(description='Sync data to production server')
    parser.add_argument('--test', action='store_true', help='Test connection only')
    parser.add_argument('--stats', action='store_true', help='Show production statistics')
    parser.add_argument('--days', type=int, default=7, help='Days of data to sync (default: 7)')
    parser.add_argument('--sensors', nargs='+', help='Specific sensor IDs to sync')
    parser.add_argument('--dry-run', action='store_true', help='Extract data but do not send')

    args = parser.parse_args()

    # Initialize clients
    sync_client = ProductionSyncClient()
    extractor = LocalDataExtractor()

    # Test connection
    if args.test or not sync_client.test_connection():
        if args.test:
            logger.info("✅ Connection test completed")
            return
        else:
            logger.error("❌ Cannot proceed - connection test failed")
            sys.exit(1)

    # Show stats if requested
    if args.stats:
        stats = sync_client.get_production_stats()
        if stats.get('success'):
            logger.info("📊 Production Database Statistics:")
            for stat in stats.get('data', []):
                logger.info(f"  {stat['parameter']}: {stat['total_points']:,} points, "
                          f"latest: {stat['latest'][:19] if stat['latest'] else 'None'}")
        return

    # Extract and sync data
    logger.info(f"🔄 Starting sync for last {args.days} days")

    data_points = extractor.get_timeseries_data(
        days_back=args.days,
        specific_sensors=args.sensors
    )

    if not data_points:
        logger.warning("⚠️  No data found to sync")
        return

    if args.dry_run:
        logger.info(f"🏃 Dry run: Would sync {len(data_points)} data points")
        return

    # Send data to production
    success = sync_client.bulk_insert_data(data_points)

    if success:
        logger.info("🎉 Sync completed successfully!")
        # Show updated stats
        stats = sync_client.get_production_stats()
        if stats.get('success'):
            logger.info("📊 Updated Production Statistics:")
            for stat in stats.get('data', []):
                logger.info(f"  {stat['parameter']}: {stat['total_points']:,} points")
    else:
        logger.error("❌ Sync failed")
        sys.exit(1)


if __name__ == "__main__":
    main()