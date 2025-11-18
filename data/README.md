# Demo Data

This folder contains sample tree inventory data for testing and development.

## Available Datasets

### Tree Inventory Data

#### ecosense_250908.csv

Real tree inventory data from forest plots collected via EcoSense mobile app.

**Contents:**

- 1,582 trees from 18 forest plots
- Tree species: Beech, Douglas Fir, Silver Fir, Spruce, Oak
- GPS coordinates (UTM 32632 projection)
- Diameter measurements and TLS tree heights
- QR code links to tree images

**Columns:**

- `fid` - Feature ID
- `species` - Tree species name
- `qr_code_id` - URL to tree image/data
- `diameter_m` - Diameter in meters
- `tls_treeheight` - Height from laser scanning
- `x_32632`, `y_32632` - UTM coordinates
- `plot_id`, `tree_id`, `full_id` - Identifiers
- `elevation` - Elevation in meters

#### mathisle_250904.csv

Tree inventory data from Mathisleweiher forest plot.

**Contents:**

- 743 trees (primarily European Beech)
- GPS coordinates (WGS84)
- Diameter at breast height (DBH)
- Tree IDs and QR codes

**Columns:**

- `species_short` - Species abbreviation (BE = Beech)
- `date_time` - Measurement timestamp
- `qr_code` - URL to tree data
- `gps_latitude`, `gps_longitude`, `gps_height` - GPS coordinates
- `DBH` - Diameter at breast height in meters
- `TreeID` - Unique tree identifier
- `species_label` - Full species name

### Sensor Time-Series Data (ecosense/)

Real environmental sensor data from Douglas Fir tree monitoring in EcoSense mixed plot.

#### <Sapflow.DouglasFir_Mixed_5_Total_SapFlow@Ecosense_MixedPlot.csv>

- **9,066 readings** of tree sap flow
- 15-minute intervals
- Unit: g/h (grams per hour)
- Date range: Aug 2024 - Aug 2025

#### <SoilMoisture.DouglasFir_Mixed_5_edge_E@Ecosense_MixedPlot.csv>

- **23,044 readings** of soil volumetric water content
- 15-minute intervals
- Unit: % (percentage)
- Location: Edge E sensor position

#### <SoilTemp.DouglasFir_Mixed_5_edge_E@Ecosense_MixedPlot.csv>

- **23,026 readings** of subsurface soil temperature
- 15-minute intervals
- Unit: °C (Celsius)
- Location: Edge E sensor position

#### <StemRadialVar.DouglasFir_Mixed_5_Dendrometer@Ecosense_MixedPlot.csv>

- **34,441 readings** of stem diameter variations
- 15-minute intervals
- Unit: mm (millimeters)
- Dendrometer on Douglas Fir tree

**Total: 89,577 sensor readings spanning 1 year**

## Importing Demo Data

**Note: These CSV files are automatically imported during database initialization!**

The migration script `19-load-csv-data.sql` automatically loads both CSV files when the database is built. The CSV files are copied to `docker/volumes/db/init/` during the build process and are loaded by the PostgreSQL `COPY` command.

### Automatic Import (Current Setup)

When you run `docker-compose up`, the following happens automatically:

**Tree Inventory Import (Migration 19):**

1. CSV files are available in `/docker-entrypoint-initdb.d/` inside the container
2. Migration script `19-load-csv-data.sql` runs automatically
3. Trees and stems data are inserted into the `trees` schema
4. Location records are created:
   - **EcoSense Forest Area** (1,502 trees from plots 1-18)
   - **Mathisleweiher Forest Plot** (735 trees)
5. **Total: 2,237 trees with 2,236 stems imported**

**Sensor Data Import (Migration 20):**

1. Sensor CSV files are mounted to the container
2. Migration script `20-load-sensor-data.sql` runs automatically
3. Creates 4 sensor records in the `sensor` schema
4. Imports time-series readings for:
   - **Sapflow**: 9,066 readings
   - **Soil Moisture**: 23,044 readings
   - **Soil Temperature**: 23,026 readings
   - **Stem Radial Variation**: 34,441 readings
5. **Total: 89,577 sensor readings spanning Aug 2024 - Aug 2025**

### Manual Re-import (If Needed)

If you need to manually re-import the data, you can run the migration script directly

### Option 2: Import via Supabase Studio

1. Open Supabase Studio: <http://localhost:54323>
2. Navigate to Table Editor
3. Select the target table (e.g., `trees.trees`)
4. Click "Insert" → "Import data from CSV"
5. Upload one of the CSV files
6. Map columns to table fields
7. Click "Import"

### Option 3: Programmatic Import

Use Python with the Supabase client:

```python
import pandas as pd
from supabase import create_client

# Load CSV
df = pd.read_csv('data/ecosense_250908.csv')

# Initialize Supabase client
supabase = create_client('http://localhost:54321', 'YOUR_ANON_KEY')

# Transform and insert data
for _, row in df.iterrows():
    supabase.table('trees').insert({
        'treeid': row['full_id'],
        'speciesid': get_species_id(row['species']),
        'locationid': get_location_id(row['plot_id']),
        'dbh': row['diameter_m'] * 100,  # convert to cm
        'height': row['tls_treeheight'],
        # ... map other fields
    }).execute()
```

## Data Privacy

**Important:** These demo datasets are provided for development and testing purposes only.

Before committing any data to the repository:

- Ensure it contains no sensitive or personal information
- Do not include proprietary research data without permission
- Add sensitive data files to `.gitignore`

For production use with sensitive data:

1. Add data files to `.gitignore`
2. Document the expected data structure without actual data
3. Share sensitive data through secure channels (not git)

---

**See Also:**

- [docker/README.md](../docker/README.md) - Database setup guide
- [README.md](../README.md) - Main project documentation
