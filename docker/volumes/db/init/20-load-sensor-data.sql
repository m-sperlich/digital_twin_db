-- XR Future Forests Lab - Sensor Data Import Migration
-- This migration imports sensor time-series data from CSV files
-- Data sources: EcoSense sensor measurements (Sapflow, SoilMoisture, SoilTemp, StemRadialVar)

-- Set search path (include extensions schema for PostGIS functions)
SET search_path TO sensor, shared, extensions, public;

-- =============================================================================
-- CREATE TEMPORARY TABLES FOR CSV IMPORT
-- =============================================================================

CREATE TEMP TABLE temp_sapflow (
    row_num INTEGER,
    timestamp TIMESTAMPTZ,
    value NUMERIC,
    parameter TEXT,
    timeseries_id TEXT
);

CREATE TEMP TABLE temp_soil_moisture (
    row_num INTEGER,
    timestamp TIMESTAMPTZ,
    value NUMERIC,
    parameter TEXT,
    timeseries_id TEXT
);

CREATE TEMP TABLE temp_soil_temp (
    row_num INTEGER,
    timestamp TIMESTAMPTZ,
    value NUMERIC,
    parameter TEXT,
    timeseries_id TEXT
);

CREATE TEMP TABLE temp_stem_radial (
    row_num INTEGER,
    timestamp TIMESTAMPTZ,
    value NUMERIC,
    parameter TEXT,
    timeseries_id TEXT
);

-- =============================================================================
-- LOAD SENSOR CSV DATA INTO TEMPORARY TABLES
-- =============================================================================

-- Load Sapflow data
COPY temp_sapflow (row_num, timestamp, value, parameter, timeseries_id)
FROM '/docker-entrypoint-initdb.d/Sapflow.DouglasFir_Mixed_5_Total_SapFlow@Ecosense_MixedPlot.csv'
WITH (FORMAT CSV, HEADER true, NULL '');

-- Load Soil Moisture data
COPY temp_soil_moisture (row_num, timestamp, value, parameter, timeseries_id)
FROM '/docker-entrypoint-initdb.d/SoilMoisture.DouglasFir_Mixed_5_edge_E@Ecosense_MixedPlot.csv'
WITH (FORMAT CSV, HEADER true, NULL '');

-- Load Soil Temperature data
COPY temp_soil_temp (row_num, timestamp, value, parameter, timeseries_id)
FROM '/docker-entrypoint-initdb.d/SoilTemp.DouglasFir_Mixed_5_edge_E@Ecosense_MixedPlot.csv'
WITH (FORMAT CSV, HEADER true, NULL '');

-- Load Stem Radial Variation data
COPY temp_stem_radial (row_num, timestamp, value, parameter, timeseries_id)
FROM '/docker-entrypoint-initdb.d/StemRadialVar.DouglasFir_Mixed_5_Dendrometer@Ecosense_MixedPlot.csv'
WITH (FORMAT CSV, HEADER true, NULL '');

-- =============================================================================
-- ADD MISSING SENSOR TYPES
-- =============================================================================

-- Add Stem Radial Variation sensor type (dendrometer)
INSERT INTO sensor.SensorTypes (SensorTypeName, Description, TypicalUnit, TypicalRangeMin, TypicalRangeMax) VALUES
    ('Stem_Radial_Variation', 'Dendrometer for measuring stem diameter changes', 'mm', -5, 20)
ON CONFLICT (SensorTypeName) DO NOTHING;

-- =============================================================================
-- CREATE SENSOR RECORDS
-- =============================================================================

-- Get the EcoSense location
DO $$
DECLARE
    ecosense_location_id INTEGER;
    ecosense_center_point extensions.GEOMETRY(Point, 4326);
    sapflow_sensor_id INTEGER;
    soil_moisture_sensor_id INTEGER;
    soil_temp_sensor_id INTEGER;
    stem_radial_sensor_id INTEGER;
BEGIN
    -- Get location details
    SELECT LocationID, CenterPoint 
    INTO ecosense_location_id, ecosense_center_point
    FROM shared.Locations 
    WHERE LocationName = 'EcoSense Forest Area' 
    LIMIT 1;

    -- Insert Sapflow sensor
    INSERT INTO sensor.Sensors (
        LocationID,
        SensorTypeID,
        SensorModel,
        SerialNumber,
        Position,
        InstallationDate,
        SamplingInterval_seconds,
        ReadingType,
        Unit,
        MinValue,
        MaxValue,
        IsActive,
        MaintenanceNotes,
        CreatedBy
    ) VALUES (
        ecosense_location_id,
        (SELECT SensorTypeID FROM sensor.SensorTypes WHERE SensorTypeName = 'Sap_Flow'),
        'EcoSense Sapflow Sensor',
        'DouglasFir_Mixed_5',
        ecosense_center_point,
        '2024-08-04 08:00:00'::TIMESTAMPTZ,
        900,  -- 15 minutes
        'Total_SapFlow',
        'g/h',
        0,
        10000,
        TRUE,
        'Douglas Fir tree in mixed plot, Plot 5',
        'ecosense_sensor_import'
    )
    RETURNING SensorID INTO sapflow_sensor_id;

    -- Insert Soil Moisture sensor
    INSERT INTO sensor.Sensors (
        LocationID,
        SensorTypeID,
        SensorModel,
        SerialNumber,
        Position,
        InstallationDate,
        SamplingInterval_seconds,
        ReadingType,
        Unit,
        MinValue,
        MaxValue,
        IsActive,
        MaintenanceNotes,
        CreatedBy
    ) VALUES (
        ecosense_location_id,
        (SELECT SensorTypeID FROM sensor.SensorTypes WHERE SensorTypeName = 'Soil_Moisture'),
        'EcoSense Soil Moisture Sensor',
        'DouglasFir_Mixed_5_edge_E',
        ecosense_center_point,
        '2024-08-04 08:00:00'::TIMESTAMPTZ,
        900,  -- 15 minutes
        'Volumetric_Water_Content',
        '%',
        0,
        100,
        TRUE,
        'Edge E location, Plot 5',
        'ecosense_sensor_import'
    )
    RETURNING SensorID INTO soil_moisture_sensor_id;

    -- Insert Soil Temperature sensor
    INSERT INTO sensor.Sensors (
        LocationID,
        SensorTypeID,
        SensorModel,
        SerialNumber,
        Position,
        InstallationDate,
        SamplingInterval_seconds,
        ReadingType,
        Unit,
        MinValue,
        MaxValue,
        IsActive,
        MaintenanceNotes,
        CreatedBy
    ) VALUES (
        ecosense_location_id,
        (SELECT SensorTypeID FROM sensor.SensorTypes WHERE SensorTypeName = 'Soil_Temperature'),
        'EcoSense Soil Temperature Sensor',
        'DouglasFir_Mixed_5_edge_E',
        ecosense_center_point,
        '2024-08-04 08:00:00'::TIMESTAMPTZ,
        900,  -- 15 minutes
        'Subsurface_Temperature',
        '°C',
        -20,
        40,
        TRUE,
        'Edge E location, Plot 5',
        'ecosense_sensor_import'
    )
    RETURNING SensorID INTO soil_temp_sensor_id;

    -- Insert Stem Radial Variation sensor (Dendrometer)
    INSERT INTO sensor.Sensors (
        LocationID,
        SensorTypeID,
        SensorModel,
        SerialNumber,
        Position,
        InstallationDate,
        SamplingInterval_seconds,
        ReadingType,
        Unit,
        MinValue,
        MaxValue,
        IsActive,
        MaintenanceNotes,
        CreatedBy
    ) VALUES (
        ecosense_location_id,
        (SELECT SensorTypeID FROM sensor.SensorTypes WHERE SensorTypeName = 'Stem_Radial_Variation'),
        'EcoSense Dendrometer',
        'DouglasFir_Mixed_5',
        ecosense_center_point,
        '2024-08-04 08:00:00'::TIMESTAMPTZ,
        900,  -- 15 minutes
        'Radial_Diameter_Change',
        'mm',
        -5,
        20,
        TRUE,
        'Douglas Fir tree in mixed plot, Plot 5',
        'ecosense_sensor_import'
    )
    RETURNING SensorID INTO stem_radial_sensor_id;

    RAISE NOTICE 'Created sensors: Sapflow=%, SoilMoisture=%, SoilTemp=%, StemRadial=%', 
        sapflow_sensor_id, soil_moisture_sensor_id, soil_temp_sensor_id, stem_radial_sensor_id;
END $$;

-- =============================================================================
-- INSERT SENSOR READINGS
-- =============================================================================

-- Insert Sapflow readings
WITH sapflow_inserts AS (
    INSERT INTO sensor.SensorReadings (
        SensorID,
        Timestamp,
        Value,
        Quality
    )
    SELECT
        (SELECT SensorID FROM sensor.Sensors 
         WHERE SerialNumber = 'DouglasFir_Mixed_5' 
         AND SensorTypeID = (SELECT SensorTypeID FROM sensor.SensorTypes WHERE SensorTypeName = 'Sap_Flow')
         LIMIT 1),
        t.timestamp,
        t.value,
        'good'
    FROM temp_sapflow t
    WHERE t.value IS NOT NULL
        AND t.timestamp IS NOT NULL
    RETURNING ReadingID
)
SELECT COUNT(*) AS sapflow_readings_imported FROM sapflow_inserts;

-- Insert Soil Moisture readings
WITH soil_moisture_inserts AS (
    INSERT INTO sensor.SensorReadings (
        SensorID,
        Timestamp,
        Value,
        Quality
    )
    SELECT
        (SELECT SensorID FROM sensor.Sensors 
         WHERE SerialNumber = 'DouglasFir_Mixed_5_edge_E' 
         AND SensorTypeID = (SELECT SensorTypeID FROM sensor.SensorTypes WHERE SensorTypeName = 'Soil_Moisture')
         LIMIT 1),
        t.timestamp,
        t.value,
        'good'
    FROM temp_soil_moisture t
    WHERE t.value IS NOT NULL
        AND t.timestamp IS NOT NULL
    RETURNING ReadingID
)
SELECT COUNT(*) AS soil_moisture_readings_imported FROM soil_moisture_inserts;

-- Insert Soil Temperature readings
WITH soil_temp_inserts AS (
    INSERT INTO sensor.SensorReadings (
        SensorID,
        Timestamp,
        Value,
        Quality
    )
    SELECT
        (SELECT SensorID FROM sensor.Sensors 
         WHERE SerialNumber = 'DouglasFir_Mixed_5_edge_E' 
         AND SensorTypeID = (SELECT SensorTypeID FROM sensor.SensorTypes WHERE SensorTypeName = 'Soil_Temperature')
         LIMIT 1),
        t.timestamp,
        t.value,
        'good'
    FROM temp_soil_temp t
    WHERE t.value IS NOT NULL
        AND t.timestamp IS NOT NULL
    RETURNING ReadingID
)
SELECT COUNT(*) AS soil_temp_readings_imported FROM soil_temp_inserts;

-- Insert Stem Radial Variation readings
WITH stem_radial_inserts AS (
    INSERT INTO sensor.SensorReadings (
        SensorID,
        Timestamp,
        Value,
        Quality
    )
    SELECT
        (SELECT SensorID FROM sensor.Sensors 
         WHERE SerialNumber = 'DouglasFir_Mixed_5' 
         AND SensorTypeID = (SELECT SensorTypeID FROM sensor.SensorTypes WHERE SensorTypeName = 'Stem_Radial_Variation')
         LIMIT 1),
        t.timestamp,
        t.value,
        'good'
    FROM temp_stem_radial t
    WHERE t.value IS NOT NULL
        AND t.timestamp IS NOT NULL
    RETURNING ReadingID
)
SELECT COUNT(*) AS stem_radial_readings_imported FROM stem_radial_inserts;

-- =============================================================================
-- SUMMARY OUTPUT
-- =============================================================================

DO $$
DECLARE
    sapflow_count INTEGER;
    soil_moisture_count INTEGER;
    soil_temp_count INTEGER;
    stem_radial_count INTEGER;
    total_readings INTEGER;
    sensor_count INTEGER;
    date_range_start TIMESTAMPTZ;
    date_range_end TIMESTAMPTZ;
BEGIN
    -- Count readings by sensor type
    SELECT COUNT(*) INTO sapflow_count 
    FROM sensor.SensorReadings sr
    JOIN sensor.Sensors s ON sr.SensorID = s.SensorID
    JOIN sensor.SensorTypes st ON s.SensorTypeID = st.SensorTypeID
    WHERE st.SensorTypeName = 'Sap_Flow' AND s.CreatedBy = 'ecosense_sensor_import';
    
    SELECT COUNT(*) INTO soil_moisture_count 
    FROM sensor.SensorReadings sr
    JOIN sensor.Sensors s ON sr.SensorID = s.SensorID
    JOIN sensor.SensorTypes st ON s.SensorTypeID = st.SensorTypeID
    WHERE st.SensorTypeName = 'Soil_Moisture' AND s.CreatedBy = 'ecosense_sensor_import';
    
    SELECT COUNT(*) INTO soil_temp_count 
    FROM sensor.SensorReadings sr
    JOIN sensor.Sensors s ON sr.SensorID = s.SensorID
    JOIN sensor.SensorTypes st ON s.SensorTypeID = st.SensorTypeID
    WHERE st.SensorTypeName = 'Soil_Temperature' AND s.CreatedBy = 'ecosense_sensor_import';
    
    SELECT COUNT(*) INTO stem_radial_count 
    FROM sensor.SensorReadings sr
    JOIN sensor.Sensors s ON sr.SensorID = s.SensorID
    JOIN sensor.SensorTypes st ON s.SensorTypeID = st.SensorTypeID
    WHERE st.SensorTypeName = 'Stem_Radial_Variation' AND s.CreatedBy = 'ecosense_sensor_import';
    
    SELECT COUNT(*) INTO total_readings 
    FROM sensor.SensorReadings sr
    JOIN sensor.Sensors s ON sr.SensorID = s.SensorID
    WHERE s.CreatedBy = 'ecosense_sensor_import';
    
    SELECT COUNT(*) INTO sensor_count 
    FROM sensor.Sensors 
    WHERE CreatedBy = 'ecosense_sensor_import';
    
    -- Get date range
    SELECT MIN(sr.Timestamp), MAX(sr.Timestamp)
    INTO date_range_start, date_range_end
    FROM sensor.SensorReadings sr
    JOIN sensor.Sensors s ON sr.SensorID = s.SensorID
    WHERE s.CreatedBy = 'ecosense_sensor_import';
    
    RAISE NOTICE '=======================================================';
    RAISE NOTICE 'Sensor Data Import Summary';
    RAISE NOTICE '=======================================================';
    RAISE NOTICE 'Sensors created: %', sensor_count;
    RAISE NOTICE 'Sapflow readings imported: %', sapflow_count;
    RAISE NOTICE 'Soil Moisture readings imported: %', soil_moisture_count;
    RAISE NOTICE 'Soil Temperature readings imported: %', soil_temp_count;
    RAISE NOTICE 'Stem Radial Variation readings imported: %', stem_radial_count;
    RAISE NOTICE 'Total readings imported: %', total_readings;
    RAISE NOTICE 'Date range: % to %', date_range_start, date_range_end;
    RAISE NOTICE '=======================================================';
END $$;
