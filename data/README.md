# Demo Data

This folder contains sample tree inventory data for testing and development.

## Available Datasets

### ecosense_250908.csv

Real tree inventory data from forest plots collected via EcoSense mobile app.

**Contents:**
- Tree species (Beech, etc.)
- GPS coordinates (UTM 32632 projection)
- Diameter measurements
- TLS (Terrestrial Laser Scanner) tree heights
- Plot and tree IDs
- QR code links to tree images
- Elevation data

**Columns:**
- `fid` - Feature ID
- `species` - Tree species name
- `qr_code_id` - URL to tree image/data
- `diameter_m` - Diameter in meters
- `tls_treeheight` - Height from laser scanning
- `x_32632`, `y_32632` - UTM coordinates
- `plot_id`, `tree_id`, `full_id` - Identifiers
- `elevation` - Elevation in meters

### mathisle_250904.csv

Tree inventory data from Mathisleweiher forest plot.

**Contents:**
- Tree species (primarily Beech - Fagus sylvatica)
- GPS coordinates (lat/lon)
- Diameter at breast height (DBH)
- Tree IDs and QR codes
- Collection timestamps

**Columns:**
- `species_short` - Species abbreviation (BE = Beech)
- `date_time` - Measurement timestamp
- `qr_code` - URL to tree data
- `gps_latitude`, `gps_longitude`, `gps_height` - GPS coordinates
- `DBH` - Diameter at breast height in meters
- `TreeID` - Unique tree identifier
- `species_label` - Full species name

## Importing Demo Data

These CSV files can be imported into the database using SQL migrations or the Supabase Studio UI.

### Option 1: Create an Import Migration

Create a new SQL file in `docker/volumes/db/init/` (e.g., `20-import-demo-data.sql`):

```sql
-- Create temporary staging table
CREATE TEMP TABLE temp_ecosense (
    fid INTEGER,
    species TEXT,
    qr_code_id TEXT,
    tree_image TEXT,
    comment TEXT,
    odk_KEY TEXT,
    x_32632 DOUBLE PRECISION,
    y_32632 DOUBLE PRECISION,
    diameter_m DOUBLE PRECISION,
    tls_treeheight DOUBLE PRECISION,
    plot_id INTEGER,
    tree_id INTEGER,
    full_id TEXT,
    elevation DOUBLE PRECISION
);

-- Copy CSV data (requires direct file access)
COPY temp_ecosense FROM '/docker-entrypoint-initdb.d/data/ecosense_250908.csv' 
WITH (FORMAT CSV, HEADER true);

-- Transform and insert into trees schema
-- (customize based on your schema structure)
```

### Option 2: Import via Supabase Studio

1. Open Supabase Studio: http://localhost:54323
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
