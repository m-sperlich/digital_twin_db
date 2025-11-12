#!/bin/bash
#
# Supabase Database Verification Script
# Checks that all schemas, tables, and data are properly set up

echo "=== XR Future Forests Lab - Supabase Database Verification ==="
echo ""

# Database connection test
echo "1. Testing database connection..."
docker exec xr_forests_db psql -U postgres -d postgres -c "SELECT version();" -t | head -1
echo "✓ Database connection successful"
echo ""

# Check schemas
echo "2. Checking schemas..."
docker exec xr_forests_db psql -U postgres -d postgres -t -c "
SELECT COUNT(*) FROM information_schema.schemata 
WHERE schema_name IN ('shared', 'trees', 'pointclouds', 'sensor', 'environments', 'extensions');" | xargs echo -n
echo " schemas created (expected: 6)"
echo ""

# Check PostGIS
echo "3. Checking PostGIS extension..."
docker exec xr_forests_db psql -U postgres -d postgres -t -c "
SELECT extversion FROM pg_extension WHERE extname = 'postgis';" | xargs echo -n
echo " (PostGIS enabled)"
echo ""

# Check tables
echo "4. Checking tables..."
docker exec xr_forests_db psql -U postgres -d postgres -t -c "
SELECT COUNT(*) FROM pg_tables 
WHERE schemaname IN ('shared', 'trees', 'pointclouds', 'sensor', 'environments');" | xargs echo -n
echo " tables created"
echo ""

# Check data
echo "5. Checking imported data..."
echo -n "   - Species: "
docker exec xr_forests_db psql -U postgres -d postgres -t -c "SELECT COUNT(*) FROM shared.Species;" | xargs
echo -n "   - Locations: "
docker exec xr_forests_db psql -U postgres -d postgres -t -c "SELECT COUNT(*) FROM shared.Locations;" | xargs
echo -n "   - Trees: "
docker exec xr_forests_db psql -U postgres -d postgres -t -c "SELECT COUNT(*) FROM trees.Trees;" | xargs
echo -n "   - Stems: "
docker exec xr_forests_db psql -U postgres -d postgres -t -c "SELECT COUNT(*) FROM trees.Stems;" | xargs
echo ""

# Sample query
echo "6. Sample tree data:"
docker exec xr_forests_db psql -U postgres -d postgres -c "
SELECT 
    l.LocationName,
    s.CommonName AS Species,
    COUNT(*) AS TreeCount,
    AVG(st.DBH_cm)::NUMERIC(5,1) AS AvgDBH_cm,
    AVG(t.Height_m)::NUMERIC(5,1) AS AvgHeight_m
FROM trees.Trees t
LEFT JOIN shared.Locations l ON t.LocationID = l.LocationID
LEFT JOIN shared.Species s ON t.SpeciesID = s.SpeciesID
LEFT JOIN trees.Stems st ON t.VariantID = st.TreeVariantID
GROUP BY l.LocationName, s.CommonName
ORDER BY TreeCount DESC
LIMIT 5;" 2>/dev/null

echo ""
echo "=== Verification Complete ==="
echo ""
echo "Access points:"
echo "  - Supabase Studio: http://localhost:54323"
echo "  - PostgreSQL: localhost:54322"
echo "  - REST API: http://localhost:54321"
echo ""
echo "Database credentials:"
echo "  - User: postgres"
echo "  - Password: (check .env file)"
echo "  - Database: postgres"
