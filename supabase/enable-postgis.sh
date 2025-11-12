#!/bin/bash
#
# Enable PostGIS Extension for Supabase
# This script works around the pg_tle extension wrapper by using psql directly

set -e

echo "Enabling PostGIS extension in Supabase database..."

# Try different approaches to enable PostGIS

# Approach 1: Try via public schema
docker exec -i xr_forests_db psql -U postgres -d postgres <<'SQL' || true
-- Disable extension wrapper temporarily (if possible)
SET session_preload_libraries = '';

-- Create PostGIS in public schema
CREATE EXTENSION IF NOT EXISTS postgis SCHEMA public CASCADE;
CREATE EXTENSION IF NOT EXISTS postgis_topology SCHEMA public CASCADE;

-- Grant permissions
GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;
GRANT ALL ON ALL TABLES IN SCHEMA public TO anon, authenticated, service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO anon, authenticated, service_role;
GRANT ALL ON ALL FUNCTIONS IN SCHEMA public TO anon, authenticated, service_role;

SELECT PostGIS_Version();
SQL

# Approach 2: If that fails, try via extensions schema
docker exec -i xr_forests_db psql -U postgres -d postgres <<'SQL' || true
CREATE SCHEMA IF NOT EXISTS extensions;
CREATE EXTENSION IF NOT EXISTS postgis SCHEMA extensions CASCADE;
CREATE EXTENSION IF NOT EXISTS postgis_topology SCHEMA extensions CASCADE;

-- Add extensions schema to search path
ALTER DATABASE postgres SET search_path TO public, extensions;

-- Grant permissions
GRANT USAGE ON SCHEMA extensions TO anon, authenticated, service_role;
GRANT ALL ON ALL TABLES IN SCHEMA extensions TO anon, authenticated, service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA extensions TO anon, authenticated, service_role;
GRANT ALL ON ALL FUNCTIONS IN SCHEMA extensions TO anon, authenticated, service_role;

SELECT PostGIS_Version();
SQL

echo "PostGIS enablement attempt complete. Checking..."
docker exec -i xr_forests_db psql -U postgres -d postgres -c "SELECT extname, extversion FROM pg_extension WHERE extname LIKE 'postgis%';"
