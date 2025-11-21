# Ecosense Data Sync

This directory contains the **unified** Python-based data synchronization system that syncs only the data needed by the R Shiny app from the Aquarius Time Series API directly to production.

## Files Overview

- **`ecosense_sync.py`** - 🎯 **Main unified sync script** (Aquarius → Production)
- **`test_connection.py`** - Quick connection test utility  
- **`environment.yml`** - Conda environment dependencies
- **`.env`** - Environment variables (configure before use)
- **`old_scripts/`** - Backup of previous multi-script approach

## Overview

The **`ecosense_sync.py`** script provides a streamlined, single-script solution that:

1. **Direct Pipeline**: Aquarius API → Production Server (no intermediate local storage)
2. **Smart Filtering**: Only syncs sensors used by the R Shiny app (5 key parameters)
3. **Flexible**: Works with or without inventory-based filtering
4. **Efficient**: Optimized for university network → production server syncing

### Key Parameters Synced

- `Sapflow`
- `StemRadialVar_Volt`
- `BarPressure`
- `SoilMoisture`
- `SoilTemp`

### Data Flow

```
🏛️ University PC → 🌊 Aquarius API → 📡 Production Server
                     (no local DB needed)
```

## Key Features

### 🎯 **Smart Sensor Filtering**

- **Basic Mode**: ~692 sensors (all Ecosense locations + target parameters)
- **Smart Mode**: ~46 sensors (only sensors linked to trees in inventory)
- **Selective**: Can sync specific sensors by ID

### ⚡ **Optimized Performance**

- **Direct streaming**: No local database storage required
- **Batch processing**: 500 data points per HTTP request
- **Rate limiting**: Built-in delays to respect API limits
- **Error resilience**: Continues if individual sensors fail
- **Progress monitoring**: Real-time sync progress with emoji indicators

### 🔄 **Flexible Operation Modes**

- **Standard sync**: `python ecosense_sync.py`
- **Test connections**: `python ecosense_sync.py --test`
- **Smart filtering**: `python ecosense_sync.py --use-inventory`
- **Dry run**: `python ecosense_sync.py --dry-run`
- **Custom timeframe**: `python ecosense_sync.py --days 30`

## Quick Start

### 1. Setup Environment

```bash
# Activate the conda environment
conda activate ecosense-data-sync

# Ensure .env file has all required variables:
# AQUARIUS_HOSTNAME, AQUARIUS_USERNAME, AQUARIUS_PASSWORD
# REMOTE_DB_HOST, PG_PROXY_TOKEN
```

### 2. Test Connections

```bash
# Test that all connections work
python ecosense_sync.py --test
```

### 3. Run Sync

```bash
# Basic sync (last 7 days, ~692 sensors)
python ecosense_sync.py

# Smart filtering (last 7 days, ~46 sensors)
python ecosense_sync.py --use-inventory

# Custom timeframe
python ecosense_sync.py --days 30

# See what would be synced without actually syncing
python ecosense_sync.py --dry-run --use-inventory
```

## Commands

- `python ecosense_sync.py` - Sync last 7 days with basic filtering (~692 sensors)
- `python ecosense_sync.py --test` - Test all connections (Aquarius + Production)
- `python ecosense_sync.py --use-inventory` - Enable smart filtering (~46 sensors)
- `python ecosense_sync.py --days N` - Sync last N days of data
- `python ecosense_sync.py --dry-run` - Show what would be synced
- `python ecosense_sync.py --sensors ID1 ID2` - Sync specific sensors only

## What Gets Synced

The script discovers and syncs relevant sensors from Ecosense locations:

**Basic Mode** (~692 sensors):

- **SoilMoisture**: ~288 sensors
- **SoilTemp**: ~288 sensors  
- **StemRadialVar_Volt**: ~57 sensors
- **BarPressure**: ~37 sensors
- **Sapflow**: ~22 sensors

**Smart Mode** (--use-inventory, ~46 sensors):

- Only sensors actually linked to trees in the inventory database
- Much faster sync, only essential data for Shiny app

Example timeseries IDs:

- `SoilMoisture.TM1_DD_2023_raw@Ecosense_Experiment_Scaffold`
- `Sapflow.Sapflow_DouglasFir_Mixed_4_Total_SapFlow@Ecosense_MixedPlot`
- `BarPressure.StemWaterPotential_DouglasFir_Mixed_4@Ecosense_MixedPlot`

## Monitoring

Check logs:

```bash
tail -f ecosense_sync.log
```

Verify data in production:

```bash
# Check production database stats
python ecosense_sync.py --test
```

## Environment Variables

Required in `.env` file:

```bash
# Aquarius connection
AQUARIUS_HOSTNAME=http://your-aquarius-server.com
AQUARIUS_USERNAME=your_username
AQUARIUS_PASSWORD=your_password

# Production server
REMOTE_DB_HOST=dt.unr.uni-freiburg.de
PG_PROXY_TOKEN=your_production_token

# Optional: Local database (for smart filtering)
LOCAL_DB_HOST=localhost
LOCAL_DB_PORT=5432
LOCAL_DB_NAME=sensors
LOCAL_DB_USER=postgres
LOCAL_DB_PASSWORD=postgres
```

## Benefits of Unified Approach

✅ **Simplified**: Single script instead of 3 separate scripts
✅ **Faster**: Direct Aquarius → Production pipeline
✅ **Portable**: No local database dependency for basic operation  
✅ **Flexible**: Multiple operation modes and filtering options
✅ **Reliable**: Built-in error handling and progress monitoring
✅ **Efficient**: Only syncs data actually needed by Shiny app

Perfect for running from your university PC to keep the production server updated with fresh sensor data!
