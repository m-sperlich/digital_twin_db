-- XR Future Forests Lab - CSV Data Import Migration
-- This migration imports tree inventory data from CSV files for testing and demo purposes
-- Data sources: ecosense_250908.csv and mathisle_250904.csv

-- Set search path (include extensions schema for PostGIS functions)
SET search_path TO trees, shared, extensions, public;

-- =============================================================================
-- ADD LOCATIONS FOR CSV DATA
-- =============================================================================

-- EcoSense Forest Area (encompasses all plots from the mobile app data)
INSERT INTO shared.Locations (LocationName, CenterPoint, Description, Elevation_m, SoilTypeID, ClimateZoneID) VALUES
    (
        'EcoSense Forest Area',
        ST_Transform(ST_GeomFromText('POINT(416710 5346650)', 32632), 4326),
        'Forest area measured via EcoSense mobile app with TLS tree heights. Contains plots 1-18. Individual tree positions stored in Position field (UTM 32632)',
        524.0,
        (SELECT SoilTypeID FROM shared.SoilTypes WHERE SoilTypeName = 'Alfisol'),
        (SELECT ClimateZoneID FROM shared.ClimateZones WHERE ClimateZoneName = 'Cfb')
    );

-- Mathisle Forest Plot (Mathisleweiher, coordinates derived from CSV data)
INSERT INTO shared.Locations (LocationName, CenterPoint, Description, Elevation_m, SoilTypeID, ClimateZoneID) VALUES
    (
        'Mathisleweiher Forest Plot',
        ST_GeomFromText('POINT(8.088 47.885)', 4326),
        'Mathisleweiher forest plot with primarily Beech (Fagus sylvatica) trees',
        1046.5,
        (SELECT SoilTypeID FROM shared.SoilTypes WHERE SoilTypeName = 'Alfisol'),
        (SELECT ClimateZoneID FROM shared.ClimateZones WHERE ClimateZoneName = 'Cfb')
    );

-- =============================================================================
-- ADD SPECIES NOT ALREADY IN DATABASE
-- =============================================================================

-- Check and add Douglas Fir
INSERT INTO shared.Species (CommonName, ScientificName, GrowthCharacteristics) VALUES
    (
        'Douglas Fir',
        'Pseudotsuga menziesii',
        '{"max_height_m": 60, "max_dbh_cm": 200, "typical_lifespan_years": 500, "growth_rate": "fast", "shade_tolerance": "moderate"}'::jsonb
    )
ON CONFLICT (ScientificName) DO NOTHING;

-- Check and add Spruce (generic - mapped from "Spruce" in CSV)
INSERT INTO shared.Species (CommonName, ScientificName, GrowthCharacteristics) VALUES
    (
        'Norway Spruce',
        'Picea abies',
        '{"max_height_m": 50, "max_dbh_cm": 150, "typical_lifespan_years": 200, "growth_rate": "fast", "shade_tolerance": "high"}'::jsonb
    )
ON CONFLICT (ScientificName) DO NOTHING;

-- =============================================================================
-- TEMPORARY TABLES FOR CSV DATA IMPORT
-- =============================================================================

-- Temporary table for EcoSense data
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

-- Temporary table for Mathisle data
CREATE TEMP TABLE temp_mathisle (
    row_num INTEGER,
    species_short TEXT,
    date_time TEXT,
    qr_code TEXT,
    tree_id_fallback TEXT,
    gps_latitude DOUBLE PRECISION,
    gps_longitude DOUBLE PRECISION,
    gps_height DOUBLE PRECISION,
    DBH DOUBLE PRECISION,
    TreeID INTEGER,
    species_label TEXT
);

-- =============================================================================
-- LOAD CSV DATA INTO TEMPORARY TABLES
-- =============================================================================

-- Load EcoSense CSV data
COPY temp_ecosense (
    fid, species, qr_code_id, tree_image, comment, odk_KEY,
    x_32632, y_32632, diameter_m, tls_treeheight,
    plot_id, tree_id, full_id, elevation
)
FROM '/docker-entrypoint-initdb.d/ecosense_250908.csv'
WITH (FORMAT CSV, HEADER true, NULL '');

-- Load Mathisle CSV data
COPY temp_mathisle (
    row_num, species_short, date_time, qr_code, tree_id_fallback,
    gps_latitude, gps_longitude, gps_height, DBH, TreeID, species_label
)
FROM '/docker-entrypoint-initdb.d/mathisle_250904.csv'
WITH (FORMAT CSV, HEADER true, NULL 'NA');

-- =============================================================================
-- HELPER FUNCTION FOR SPECIES MAPPING
-- =============================================================================

CREATE OR REPLACE FUNCTION get_species_id_by_name(species_name TEXT)
RETURNS INTEGER AS $$
DECLARE
    result_id INTEGER;
BEGIN
    -- Map common names to scientific names
    result_id := CASE
        WHEN LOWER(species_name) LIKE '%beech%' OR LOWER(species_name) = 'be' THEN
            (SELECT SpeciesID FROM shared.Species WHERE ScientificName = 'Fagus sylvatica')
        WHEN LOWER(species_name) LIKE '%silver fir%' THEN
            (SELECT SpeciesID FROM shared.Species WHERE ScientificName = 'Abies alba')
        WHEN LOWER(species_name) LIKE '%douglas%' THEN
            (SELECT SpeciesID FROM shared.Species WHERE ScientificName = 'Pseudotsuga menziesii')
        WHEN LOWER(species_name) LIKE '%spruce%' THEN
            (SELECT SpeciesID FROM shared.Species WHERE ScientificName = 'Picea abies')
        WHEN LOWER(species_name) LIKE '%oak%' THEN
            (SELECT SpeciesID FROM shared.Species WHERE ScientificName = 'Quercus robur')
        WHEN LOWER(species_name) LIKE '%pine%' THEN
            (SELECT SpeciesID FROM shared.Species WHERE ScientificName = 'Pinus sylvestris')
        ELSE NULL
    END;
    
    RETURN result_id;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- INSERT ECOSENSE TREES INTO DATABASE
-- =============================================================================

-- Insert trees with fid in FieldNotes for later matching
WITH ecosense_tree_inserts AS (
    INSERT INTO trees.Trees (
        LocationID,
        VariantTypeID,
        SpeciesID,
        TreeStatusID,
        Height_m,
        Position,
        FieldNotes,
        CreatedBy
    )
    SELECT
        (SELECT LocationID FROM shared.Locations 
         WHERE LocationName = 'EcoSense Forest Area' LIMIT 1),
        (SELECT VariantTypeID FROM shared.VariantTypes WHERE VariantTypeName = 'manual'),
        get_species_id_by_name(t.species),
        (SELECT TreeStatusID FROM trees.TreeStatus WHERE TreeStatusName = 'healthy'),
        t.tls_treeheight,
        ST_Transform(ST_GeomFromText('POINT(' || t.x_32632 || ' ' || t.y_32632 || ')', 32632), 4326),
        CONCAT_WS(' | ',
            'FID: ' || t.fid,
            'Plot: ' || t.plot_id,
            'TreeID: ' || t.full_id,
            'QR Code: ' || t.qr_code_id,
            CASE WHEN t.comment IS NOT NULL AND t.comment != '' THEN 'Comment: ' || t.comment ELSE NULL END
        ),
        'ecosense_csv_import'
    FROM temp_ecosense t
    WHERE t.species IS NOT NULL
        AND x_32632 IS NOT NULL
        AND t.y_32632 IS NOT NULL
    RETURNING VariantID
)
SELECT COUNT(*) AS ecosense_trees_imported FROM ecosense_tree_inserts;

-- =============================================================================
-- INSERT ECOSENSE STEMS INTO DATABASE
-- =============================================================================

WITH ecosense_stem_inserts AS (
    INSERT INTO trees.Stems (
        TreeVariantID,
        StemNumber,
        TaperTypeID,
        StraightnessTypeID,
        DBH_cm,
        StemHeight_m
    )
    SELECT DISTINCT ON (tr.VariantID)
        tr.VariantID,
        1,  -- Assuming single-stem trees
        (SELECT TaperTypeID FROM trees.TaperTypes WHERE TaperTypeName = 'Paraboloid'),
        (SELECT StraightnessTypeID FROM trees.StraightnessTypes WHERE StraightnessName = 'Straight'),
        t.diameter_m * 100,  -- Convert meters to centimeters
        t.tls_treeheight
    FROM temp_ecosense t
    JOIN trees.Trees tr ON 
        tr.FieldNotes LIKE 'FID: ' || t.fid || ' |%'
        AND tr.CreatedBy = 'ecosense_csv_import'
    WHERE t.diameter_m IS NOT NULL
        AND t.diameter_m > 0
    RETURNING StemID
)
SELECT COUNT(*) AS ecosense_stems_imported FROM ecosense_stem_inserts;

-- =============================================================================
-- INSERT MATHISLE TREES INTO DATABASE
-- =============================================================================

WITH mathisle_tree_inserts AS (
    INSERT INTO trees.Trees (
        LocationID,
        VariantTypeID,
        SpeciesID,
        TreeStatusID,
        Position,
        FieldNotes,
        CreatedBy
    )
    SELECT
        (SELECT LocationID FROM shared.Locations 
         WHERE LocationName = 'Mathisleweiher Forest Plot'),
        (SELECT VariantTypeID FROM shared.VariantTypes WHERE VariantTypeName = 'manual'),
        get_species_id_by_name(t.species_short),
        (SELECT TreeStatusID FROM trees.TreeStatus WHERE TreeStatusName = 'healthy'),
        ST_GeomFromText('POINT(' || t.gps_longitude || ' ' || t.gps_latitude || ')', 4326),
        CONCAT_WS(' | ',
            'Row: ' || t.row_num,
            CASE WHEN t.TreeID IS NOT NULL THEN 'TreeID: ' || t.TreeID::TEXT ELSE NULL END,
            'QR Code: ' || t.qr_code,
            'Measured: ' || t.date_time,
            'Species: ' || t.species_label
        ),
        'mathisle_csv_import'
    FROM temp_mathisle t
    WHERE t.species_short IS NOT NULL
        AND t.gps_latitude IS NOT NULL
        AND t.gps_longitude IS NOT NULL
    RETURNING VariantID
)
SELECT COUNT(*) AS mathisle_trees_imported FROM mathisle_tree_inserts;

-- =============================================================================
-- INSERT MATHISLE STEMS INTO DATABASE
-- =============================================================================

WITH mathisle_stem_inserts AS (
    INSERT INTO trees.Stems (
        TreeVariantID,
        StemNumber,
        TaperTypeID,
        StraightnessTypeID,
        DBH_cm
    )
    SELECT DISTINCT ON (tr.VariantID)
        tr.VariantID,
        1,  -- Assuming single-stem trees
        (SELECT TaperTypeID FROM trees.TaperTypes WHERE TaperTypeName = 'Paraboloid'),
        (SELECT StraightnessTypeID FROM trees.StraightnessTypes WHERE StraightnessName = 'Straight'),
        t.DBH * 100  -- Convert meters to centimeters
    FROM temp_mathisle t
    JOIN trees.Trees tr ON 
        tr.FieldNotes LIKE 'Row: ' || t.row_num || ' |%'
        AND tr.CreatedBy = 'mathisle_csv_import'
    WHERE t.DBH IS NOT NULL
        AND t.DBH > 0
    RETURNING StemID
)
SELECT COUNT(*) AS mathisle_stems_imported FROM mathisle_stem_inserts;

-- =============================================================================
-- CLEANUP
-- =============================================================================

DROP FUNCTION IF EXISTS get_species_id_by_name(TEXT);

-- =============================================================================
-- SUMMARY OUTPUT
-- =============================================================================

DO $$
DECLARE
    ecosense_count INTEGER;
    mathisle_count INTEGER;
    total_trees INTEGER;
    total_stems INTEGER;
BEGIN
    -- Count imported data
    SELECT COUNT(*) INTO ecosense_count FROM trees.Trees WHERE CreatedBy = 'ecosense_csv_import';
    SELECT COUNT(*) INTO mathisle_count FROM trees.Trees WHERE CreatedBy = 'mathisle_csv_import';
    SELECT COUNT(*) INTO total_trees FROM trees.Trees WHERE CreatedBy IN ('ecosense_csv_import', 'mathisle_csv_import');
    SELECT COUNT(*) INTO total_stems FROM trees.Stems s 
        JOIN trees.Trees t ON s.TreeVariantID = t.VariantID 
        WHERE t.CreatedBy IN ('ecosense_csv_import', 'mathisle_csv_import');
    
    RAISE NOTICE '======================================================';
    RAISE NOTICE 'CSV Data Import Summary';
    RAISE NOTICE '======================================================';
    RAISE NOTICE 'EcoSense trees imported: %', ecosense_count;
    RAISE NOTICE 'Mathisle trees imported: %', mathisle_count;
    RAISE NOTICE 'Total trees imported: %', total_trees;
    RAISE NOTICE 'Total stems imported: %', total_stems;
    RAISE NOTICE '======================================================';
END $$;

-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON TABLE trees.Trees IS 'Includes tree data from EcoSense mobile app (Plot 16 & 8) and Mathisleweiher forest plot';

