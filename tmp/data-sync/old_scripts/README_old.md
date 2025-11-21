# Ecosense Data Sync

This directory contains the unified Python-based data synchronization system that syncs only the data needed by the R Shiny app from the Aquarius Time Series API directly to production.

## Files Overview

- **`ecosense_sync.py`** - 🎯 **Main unified sync script** (Aquarius → Production)
- **`test_connection.py`** - Quick connection test utility
- **`environment.yml`** - Conda environment dependencies
- **`.env`** - Environment variables (configure before use)
- **`old_scripts/`** - Backup of previous multi-script approach

## Overview

The **`ecosense_sync.py`** script provides a streamlined, single-script solution that:1. **Targeted Sync**: Only syncs the 5 parameters used by the R Shiny app:
   - `Sapflow`
   - `StemRadialVar_Volt`
   - `BarPressure`
   - `SoilMoisture`
   - `SoilTemp`

2. **Ecosense Focused**: Only processes `Ecosense_*` locations (ignoring thousands of other locations)

3. **Efficient**: Reduced from 17,815 total time series to 1,331 relevant sensors

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

### � **Flexible Operation Modes**

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

The script discovers and syncs:

- **692 sensors** from Ecosense locations (filtered by inventory links)
- **SoilMoisture**: 288 sensors
- **SoilTemp**: 288 sensors  
- **StemRadialVar_Volt**: 57 sensors
- **BarPressure**: 37 sensors
- **Sapflow**: 22 sensors

Example timeseries IDs:

- `SoilMoisture.TM1_DD_2023_raw@Ecosense_Experiment_Scaffold`
- `Sapflow.Sapflow_DouglasFir_Mixed_4_Total_SapFlow@Ecosense_MixedPlot`
- `BarPressure.StemWaterPotential_DouglasFir_Mixed_4@Ecosense_MixedPlot`

## R Shiny App Integration

The script syncs data in the exact format expected by the R Shiny app:

1. **Metadata**: Updates `ecosense.ecosense_sensors` table
2. **Time Series Data**: Stores in `ecosense.timeseries_data` table
3. **ID Format**: Uses `parameter.label@location` format matching R app queries

When `ENABLE_AQUARIUS=false` in the R app, it will use this synced database data instead of calling the Aquarius API directly.

## Monitoring

Check logs:

```bash
tail -f ecosense_focused_sync.log
```

Verify data in database:

```sql
-- Check latest sync status
SELECT 
    parameter,
    COUNT(*) as sensor_count,
    MAX(timestamp) as latest_data
FROM ecosense.timeseries_data 
GROUP BY parameter
ORDER BY parameter;
```

## Production Deployment

Create a systemd service for continuous syncing:

```ini
# /etc/systemd/system/ecosense-sync.service
[Unit]
Description=Ecosense Focused Data Sync
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/ecosense-shiny/src/data-sync
Environment=PATH=/opt/miniconda3/envs/ecosense-data-sync/bin
ExecStart=/opt/miniconda3/envs/ecosense-data-sync/bin/python main.py --schedule
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl enable ecosense-sync
sudo systemctl start ecosense-sync
```
