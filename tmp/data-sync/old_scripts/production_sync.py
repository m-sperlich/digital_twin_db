#!/usr/bin/env python3
"""
Production Sync Script
Syncs all sensors to production server in an efficient, monitored way.
"""

import logging
import sys
import time
from datetime import datetime

from dotenv import load_dotenv
from main import EcosenseDataSyncer

# Load environment variables
load_dotenv()

# Setup logging with both file and console output
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("production_sync.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def sync_all_sensors_to_production(days_back=7, batch_size=50):
    """Sync all 692 sensors to production in batches with progress monitoring"""
    logger.info(
        f"🚀 Starting production sync: {days_back} days, batch size {batch_size}"
    )
    start_time = datetime.now()

    syncer = EcosenseDataSyncer()

    if not syncer.aquarius.connect():
        logger.error("❌ Failed to connect to AQUARIUS")
        return False

    try:
        # Connect to databases
        if not syncer.db.connect_local():
            logger.error("❌ Failed to connect to local database")
            return False

        if not syncer.db.test_remote_connection():
            logger.error("❌ Failed to connect to remote production server")
            return False

        logger.info("✅ All connections established")

        # Get all sensors
        sensors = syncer.aquarius.get_ecosense_sensors_for_r_app(syncer.db)
        if not sensors:
            logger.error("❌ No sensors found")
            return False

        total_sensors = len(sensors)
        logger.info(f"📊 Found {total_sensors} sensors to sync")

        # Sync metadata first
        logger.info("📝 Syncing sensor metadata to local database...")
        metadata_success = 0
        for sensor in sensors:
            if syncer.db.upsert_sensor_metadata(sensor):
                metadata_success += 1

        logger.info(f"✅ Metadata: {metadata_success}/{total_sensors} sensors")

        # Sync time series data in batches
        logger.info(f"📡 Starting time series data sync to production server...")
        logger.info(
            f"   Target: https://dt.unr.uni-freiburg.de/api/db/timeseries/bulk-insert"
        )

        success_count = 0
        error_count = 0
        no_data_count = 0
        total_data_points = 0

        for i, sensor in enumerate(sensors, 1):
            try:
                # Progress indicator
                progress = (i / total_sensors) * 100
                logger.info(
                    f"📊 Progress: {i}/{total_sensors} ({progress:.1f}%) - {sensor.parameter}.{sensor.label}"
                )

                # Sync this sensor
                result = syncer.sync_sensor_data(sensor, days_back)

                if result:
                    success_count += 1
                    # Try to get count from recent log message (rough estimate)
                    logger.info(f"   ✅ Success")
                else:
                    error_count += 1
                    logger.warning(f"   ❌ Failed")

                # Add delay every batch_size sensors to avoid overwhelming the server
                if i % batch_size == 0:
                    logger.info(
                        f"🔄 Batch completed ({i}/{total_sensors}). Pausing 5 seconds..."
                    )
                    time.sleep(5)
                else:
                    time.sleep(2)  # Standard delay between sensors

            except Exception as e:
                error_count += 1
                logger.error(f"❌ Error syncing {sensor.timeseries_identifier}: {e}")

        # Final summary
        end_time = datetime.now()
        duration = end_time - start_time

        logger.info(f"")
        logger.info(f"🎉 PRODUCTION SYNC COMPLETED!")
        logger.info(f"📊 Final Results:")
        logger.info(f"   ✅ Successful: {success_count}")
        logger.info(f"   ❌ Failed: {error_count}")
        logger.info(f"   📊 Total sensors: {total_sensors}")
        logger.info(f"   ⏱️  Duration: {duration}")
        logger.info(f"   📡 Target server: dt.unr.uni-freiburg.de")

        success_rate = (success_count / total_sensors) * 100
        logger.info(f"   📈 Success rate: {success_rate:.1f}%")

        if success_rate >= 90:
            logger.info("🎉 Sync completed successfully!")
        elif success_rate >= 70:
            logger.warning("⚠️  Sync completed with some issues")
        else:
            logger.error("❌ Sync completed with significant issues")

        return success_count > 0

    finally:
        syncer.aquarius.disconnect()
        syncer.db.close_connections()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Production Sync for Ecosense Data")
    parser.add_argument(
        "--days", type=int, default=7, help="Days back to sync (default: 7)"
    )
    parser.add_argument(
        "--batch",
        type=int,
        default=50,
        help="Batch size for rate limiting (default: 50)",
    )
    parser.add_argument(
        "--quick", action="store_true", help="Quick test with 10 sensors"
    )

    args = parser.parse_args()

    if args.quick:
        logger.info("🧪 Running quick test with first 10 sensors")
        # We'll implement a quick version if needed
        print("Quick test not implemented yet. Use regular sync with --days 1")
    else:
        success = sync_all_sensors_to_production(args.days, args.batch)
        sys.exit(0 if success else 1)
