# Demo Data

This folder contains sample data used for development and testing.

## tree_inventory_250908.csv

**Purpose**: Real tree inventory data from forest plots, used to populate the database with realistic measurements.

**Usage**: This CSV is imported via the migration file `supabase/migrations/009_import_tree_inventory.sql`.

**Contents**:
- Approximately 1,500 tree measurements
- Multiple forest plot locations
- Various tree species (Beech, Oak, Spruce, Fir, Pine)
- Measurements include: DBH (diameter at breast height), height, coordinates

**When is it loaded?**
- Automatically on first database startup
- The migration creates a staging table, imports the CSV, then transforms and inserts the data into the proper schema

**File Details**:
- Format: CSV (Comma-Separated Values)
- Size: ~320 KB
- Columns: See migration file for complete column mapping

## How Demo Data is Used

### Development and Testing
- Provides realistic data for testing queries
- Allows developers to experiment without creating test data manually
- Demonstrates proper data structure and relationships

### Learning
- New team members can explore real forest data
- Examples show how different species, locations, and measurements are stored
- Useful for understanding spatial queries and relationships

## Updating or Replacing Demo Data

If you want to use different data:

1. **Replace the CSV file**: Place your CSV in this folder
2. **Update the migration**: Edit `supabase/migrations/009_import_tree_inventory.sql` to match your column names
3. **Reset the database**:
   ```bash
   docker compose down -v
   docker compose up -d
   ```

**Important**: Migration 009 includes column mapping. If your CSV has different columns, you'll need to update the `INSERT INTO` statement in the migration file.

## Data Privacy

**Note**: This demo data should not contain sensitive or personal information. If you're working with real research data that needs protection, do not commit it to the repository. Instead:

1. Add your data file to `.gitignore`
2. Document the data structure without including the actual data
3. Share sensitive data through secure channels (not git)

---

**See Also**:
- [supabase/migrations/009_import_tree_inventory.sql](../supabase/migrations/009_import_tree_inventory.sql) - Import script
- [docs/architecture/database.md](../docs/architecture/database.md) - Database schema documentation
