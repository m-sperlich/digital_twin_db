#!/usr/bin/env python3
"""
Connection Test Script
Quick test to verify that all connections (Aquarius, local DB, remote DB) are working.
"""

import logging
import sys
from dotenv import load_dotenv
from main import EcosenseDataSyncer

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def test_all_connections():
    """Test all required connections"""
    logger.info("🔄 Testing all connections...")
    
    syncer = EcosenseDataSyncer()
    all_good = True
    
    # Test Aquarius connection
    logger.info("1. Testing Aquarius connection...")
    if syncer.aquarius.connect():
        logger.info("   ✅ Aquarius: Connected successfully")
        syncer.aquarius.disconnect()
    else:
        logger.error("   ❌ Aquarius: Connection failed")
        all_good = False
    
    # Test local database
    logger.info("2. Testing local database connection...")
    if syncer.db.connect_local():
        logger.info("   ✅ Local DB: Connected successfully")
    else:
        logger.error("   ❌ Local DB: Connection failed")
        all_good = False
    
    # Test remote database (production)
    logger.info("3. Testing remote database connection...")
    if syncer.db.test_remote_connection():
        logger.info("   ✅ Remote DB: Connected successfully")
    else:
        logger.error("   ❌ Remote DB: Connection failed")
        all_good = False
    
    # Clean up
    syncer.db.close_connections()
    
    # Summary
    if all_good:
        logger.info("🎉 All connections successful! Ready to sync.")
        return True
    else:
        logger.error("❌ Some connections failed. Check your .env file and network.")
        return False


if __name__ == "__main__":
    success = test_all_connections()
    sys.exit(0 if success else 1)