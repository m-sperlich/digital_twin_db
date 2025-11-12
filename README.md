# Digital Twin Database - XR Future Forests Lab

> **Supabase-powered data tier for forest research and XR visualization**
> University of Freiburg, Department of Forest Sciences
> Target: August 15, 2025

This repository provides the database infrastructure for creating digital twins of forests through immersive XR technologies. It uses Supabase to deliver a complete PostgreSQL-based data platform with auto-generated REST APIs, real-time subscriptions, and integrated authentication.

---

## Quick Start

### Prerequisites

- **Git** - To clone this repository
- **Docker Desktop** - v20.10+ ([Download](https://www.docker.com/products/docker-desktop/))
- **8GB RAM** minimum (16GB recommended)
- **20GB free disk space**

### Installation

Get the database running locally in 3 steps:

```bash
# 1. Clone the repository
git clone <repository-url>
cd digital_twin_db

# 2. Generate secure configuration (uses Docker, no Node.js needed!)
./utils/generate-keys.sh --write

# 3. Start the Supabase stack
docker compose --env-file .env -f docker/docker-compose.yml up -d

# Wait ~30 seconds for all services to become healthy:
docker ps --filter "name=xr_forests" --format "table {{.Names}}\t{{.Status}}"

# 4. Enable PostGIS extension via Supabase Studio (REQUIRED)
# PostGIS must be enabled manually through the Supabase Studio UI.
#
# Steps:
#   a) Open Supabase Studio: http://localhost:54323
#   b) Navigate to: Database → Extensions (in left sidebar)
#   c) Search for "postgis" → toggle to enable
#   d) In the prompt, select "Create a new schema" → name it "extensions"
#   e) Also enable "postgis_topology" the same way
#
# Verify PostGIS is enabled:
docker exec xr_forests_db psql -U postgres -d postgres -c "SELECT extensions.postgis_version();"

# 5. Apply PostGIS-dependent migrations
# After enabling PostGIS, apply the remaining schema migrations:
for f in supabase/post-setup-migrations/*.sql; do
  echo "Applying: $(basename $f)"
  docker exec -i xr_forests_db psql -U postgres -d postgres < "$f"
done

# Verify migrations completed:
docker exec xr_forests_db psql -U postgres -d postgres -c "\dt shared.*"
```

**What does key generation do?**

- Creates a `.env` file with all necessary configuration
- Generates secure random passwords and API keys
- Uses cryptography to create authentication tokens

**Important**: Never commit the `.env` file to git! It contains secrets and is already in `.gitignore`.

### Access Points

Once running, access the database through:

- **Supabase Studio UI**: <http://localhost:54323> - Visual database management
- **REST API**: <http://localhost:54321/rest/v1> - Auto-generated endpoints
- **PostgreSQL**: `localhost:54322` - Direct database access

### Verify Installation

Check that all services are running:

```bash
docker compose --env-file .env -f docker/docker-compose.yml ps
```

All services should show "Up" status. If any show "Exit" or "Restarting", see [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

**New to Supabase?** See [docs/SUPABASE_INTRO.md](docs/SUPABASE_INTRO.md) to learn what Supabase is and how it works.

---

## What's in This Repository

### Database Infrastructure

This repository implements the data tier of the XR Future Forests Lab using **Supabase**, providing:

- **PostgreSQL + PostGIS** - Spatial database with forest-specific schemas
- **PostgREST** - Automatically generated REST APIs from database structure
- **Real-time Server** - WebSocket support for live data updates
- **Authentication** - Built-in user management and Row-Level Security
- **Storage API** - S3-compatible storage for point cloud files
- **Edge Functions** - Serverless business logic (Deno/TypeScript)
- **Supabase Studio** - Visual database management interface

### Multi-Repository Architecture

This is the **data tier** of a larger system:

- **📋 Planning Hub** - Central coordination and architecture documentation
- **🌲 The Grove** - Tree asset generation service (consumes Tree API)
- **☁️ Potree Docker** - Point cloud processing service (uses Point Cloud API)

---

## Database Structure

The database organizes forest research data into 5 specialized schemas:

### 1. **shared** - Reference Data

Core reference tables used across all schemas:

- **Species** - Tree species definitions (Beech, Oak, Spruce, etc.)
- **Locations** - Forest plot coordinates and metadata
- **SoilTypes** - Soil classification system
- **ClimateZones** - Climate zone definitions
- **Processes** - Audit trail for all database changes

### 2. **pointclouds** - LiDAR Data

Point cloud scan management:

- **PointClouds** - Scan metadata with S3 file paths
- Supports multiple processing variants (raw, filtered, classified)
- Tracks processing status and quality metrics

### 3. **trees** - Tree Measurements

Individual tree data and simulations:

- **Trees** - Tree measurements and attributes
- **Stems** - Multi-stem support for complex trees
- **TreeSimulations** - Growth model outputs and predictions

### 4. **sensor** - Environmental Monitoring

IoT sensor data collection:

- **Sensors** - Sensor installations and configurations
- **SensorReadings** - Time-series environmental data

### 5. **environments** - Environmental Conditions

Processed environmental data:

- **EnvironmentalConditions** - Temperature, humidity, soil moisture
- Derived from sensors, manual input, or model outputs

All tables include:

- **Variant tracking** - Version control for data iterations
- **Audit logging** - Full change history with user attribution
- **Row-Level Security** - Fine-grained access control

---

## How to Use

### Option 1: Visual Interface (Supabase Studio)

Open <http://localhost:54323> in your browser.

**Table Editor** - Browse and edit data:

1. Select a schema in the left sidebar
2. Click on a table to view its contents
3. Add, edit, or delete rows directly

**SQL Editor** - Run custom queries:

```sql
-- Example: Get all beech trees
SELECT t.*, s.speciesname
FROM trees.trees t
JOIN shared.species s ON t.speciesid = s.speciesid
WHERE s.speciesname = 'Fagus sylvatica';
```

**API Documentation** - View auto-generated endpoints for every table.

### Option 2: REST API

The database automatically provides REST endpoints for all tables.

**API Base URL**: `http://localhost:54321/rest/v1`
**API Key**: Find `SUPABASE_ANON_KEY` in your `.env` file

**Example using curl**:

```bash
# Get all species
curl "http://localhost:54321/rest/v1/species?select=*" \
  -H "apikey: YOUR_ANON_KEY" \
  -H "Authorization: Bearer YOUR_ANON_KEY"

# Get trees with species information
curl "http://localhost:54321/rest/v1/trees?select=*,species(*)" \
  -H "apikey: YOUR_ANON_KEY" \
  -H "Authorization: Bearer YOUR_ANON_KEY"

# Create a new location
curl -X POST "http://localhost:54321/rest/v1/locations" \
  -H "apikey: YOUR_ANON_KEY" \
  -H "Authorization: Bearer YOUR_ANON_KEY" \
  -H "Content-Type: application/json" \
  -d '{"locationname":"New Plot","latitude":48.0,"longitude":8.0}'
```

**Example using Python**:

```python
from supabase import create_client

# Initialize client
supabase = create_client(
    "http://localhost:54321",
    "YOUR_ANON_KEY"  # from .env file
)

# Query data
response = supabase.table('species').select('*').execute()
print(response.data)

# Insert data
response = supabase.table('locations').insert({
    'locationname': 'Test Plot',
    'latitude': 48.0,
    'longitude': 8.0
}).execute()
```

**Example using R**:

```r
library(httr)

# Your API key from .env
api_key <- "YOUR_ANON_KEY"

# Make request
response <- GET(
  "http://localhost:54321/rest/v1/species?select=*",
  add_headers(
    apikey = api_key,
    Authorization = paste("Bearer", api_key)
  )
)

# Parse response
data <- content(response)
```

### Option 3: Direct PostgreSQL Connection

Connect with any PostgreSQL client (psql, DBeaver, pgAdmin, etc.):

```
Host: localhost
Port: 54322
Database: postgres
Username: postgres
Password: (from POSTGRES_PASSWORD in .env)
```

**Using psql**:

```bash
# Connect
docker exec -it xr_forests_db psql -U postgres

# List schemas
\dn

# List tables
\dt shared.*

# Query
SELECT * FROM shared.species;

# Exit
\q
```

---

## Project Vision

The XR Future Forests Lab creates comprehensive digital forest ecosystems for research, education, and stakeholder engagement.

### Research Applications

- **Digital Forest Twins** - Complete digital replicas with real-time data integration
- **Process Visualization** - Make invisible processes (sap flow, root competition) visible
- **Growth Modeling** - Integration with SILVA and other simulation models
- **Multi-scale Analysis** - From individual trees to landscape dynamics

### Training and Simulation

- **Immersive Visualization** - Experience forests in ways impossible in field studies
- **Decision Support** - Practice management scenarios without real-world consequences
- **Temporal Dynamics** - Visualize decades of change in accelerated time
- **Interactive Analysis** - Transform complex data into intuitive experiences

### Stakeholder Engagement

- **Policy Communication** - Accessible visualizations for decision-makers
- **Public Outreach** - Make forest science engaging for broader audiences
- **Interdisciplinary Collaboration** - Bridge forestry, technology, and policy
- **Industry Partnerships** - Practical tools for modern forest management

---

## Documentation

### Getting Started

- **[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)** - Common issues and solutions

### Technical Documentation

- **[System Architecture](docs/architecture/architecture.md)** - Three-tier system design
- **[Database Design](docs/architecture/database.md)** - Schema specifications and ERD
- **[API Architecture](docs/architecture/api.md)** - PostgREST endpoint reference
- **[Supabase Setup](docs/supabase/setup-guide.md)** - Production deployment guide
- **[S3 Integration](docs/supabase/s3-integration.md)** - Point cloud storage configuration

### Reference Guides

- **[Quick Reference](docs/QUICK_REFERENCE.md)** - Common commands and URLs
- **[Tech Stack](docs/tech-stack.md)** - Technology overview
- **[Verification Guide](docs/VERIFICATION_GUIDE.md)** - Testing procedures

---

## Development Workflow

### Starting and Stopping

```bash
# Start all services
docker compose --env-file .env -f docker/docker-compose.yml up -d

# Stop all services
docker compose --env-file .env -f docker/docker-compose.yml down

# View status
docker compose --env-file .env -f docker/docker-compose.yml ps

# View logs
docker compose --env-file .env -f docker/docker-compose.yml logs -f
```

### Working with Data

**Add sample data**:

- Use Supabase Studio UI for manual entry
- Use REST API for programmatic insertion
- Write SQL migrations in `supabase/migrations/`

**Update database schema**:

1. Create new migration file: `supabase/migrations/010_your_changes.sql`
2. Write SQL DDL commands
3. Restart database: `docker compose --env-file .env -f docker/docker-compose.yml restart db`

**Create Edge Functions**:

1. Create directory: `supabase/functions/my-function/`
2. Add `index.ts` with Deno code
3. Restart functions: `docker compose --env-file .env -f docker/docker-compose.yml restart functions`

### Testing APIs

```bash
# Set your API key
export SUPABASE_KEY="your_anon_key"

# Test endpoints
curl "http://localhost:54321/rest/v1/species?select=*" \
  -H "apikey: $SUPABASE_KEY" \
  -H "Authorization: Bearer $SUPABASE_KEY"
```

---

## S3 Storage for Point Clouds (Optional)

Large LiDAR files (.las, .laz) can be stored in external S3 buckets rather than the database.

**Note**: S3 storage is **optional**. The database works perfectly fine for tree measurements, sensor data, and locations without S3. Only configure S3 if you're working with point cloud files.

**How it works** (when configured):

1. Database stores S3 file paths: `s3://bucket-name/path/file.las`
2. Edge Functions generate presigned URLs for secure access
3. Clients download directly from S3

**Benefits**:

- Unlimited storage capacity
- Cost-effective for large files
- No database bloat
- Direct downloads with temporary URLs

**Configuration**:
See [S3 Integration Guide](docs/supabase/s3-integration.md) for setup instructions (only needed if using point clouds).

---

## Production Deployment

This repository is designed for both local development and production deployment.

### Local Development

- Use default configuration from `.env.template`
- Run on `localhost` with Docker Compose
- Simple passwords acceptable for local testing
- Start with: `docker compose --env-file .env -f docker/docker-compose.yml up -d`

### Production Server

- Use strong cryptographic keys (generate with `openssl rand -base64 32`)
- Configure domain names and SSL/TLS certificates
- Set up S3 bucket with proper IAM permissions
- Configure backups and monitoring
- Disable public signup (`DISABLE_SIGNUP=true`)

**See [Supabase Setup Guide](docs/supabase/setup-guide.md) for detailed production deployment instructions.**

---

## Integration with Other Services

External repositories consume this database through the REST API:

### The Grove (Tree Asset Generation)

```javascript
import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  'http://your-server.com:54321',
  'your_anon_key'
)

// Fetch tree data for 3D model generation
const { data } = await supabase
  .from('trees')
  .select('*, species(*), stems(*)')
  .eq('locationid', 15)
```

### Potree Docker (Point Cloud Processing)

```python
import requests

# Store processing results
requests.post(
    'http://your-server.com:54321/rest/v1/pointclouds',
    headers={'apikey': 'your_anon_key'},
    json={
        'parentvariantid': 123,
        'varianttypeid': 2,
        'processingstatus': 'completed',
        'filepath': 's3://bucket/processed.las'
    }
)
```

---

## Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Database** | PostgreSQL 15 + PostGIS | Spatial data storage |
| **API Layer** | PostgREST | Auto-generated REST endpoints |
| **Gateway** | Kong | API routing and rate limiting |
| **Authentication** | GoTrue | User management and JWT |
| **Real-time** | Supabase Realtime | WebSocket subscriptions |
| **Storage** | Supabase Storage + S3 | File storage and management |
| **Functions** | Deno Edge Runtime | Serverless business logic |
| **UI** | Supabase Studio | Database management |
| **Deployment** | Docker Compose | Container orchestration |

---

## Current Status

### ✅ Completed (Milestone 2)

- Complete Supabase Docker Compose stack
- PostgreSQL + PostGIS with 5 specialized schemas
- 10 SQL migrations with sample data
- Row-level security policies
- PostgREST auto-generated APIs
- Real-time subscription support
- Edge Functions framework
- S3 integration for point clouds
- Comprehensive documentation

### 🔄 In Progress (Milestone 3)

- Production server deployment
- Production environment configuration
- SSL/TLS certificate setup
- External service integration
- Backup and monitoring systems
- Performance optimization

**Target: August 15, 2025** - Core database operational for VR integration

---

## Requirements

### Local Development

- **Docker Desktop** - v20.10+
- **Docker Compose** - v2.0+
- **Node.js** - v16+ (for key generation)
- **8GB RAM** minimum (16GB recommended)
- **20GB disk space**

### Production Deployment

- **Linux Server** - Ubuntu 22.04 LTS recommended
- **16GB+ RAM**
- **100GB+ SSD storage**
- **Domain name** with DNS
- **S3 bucket** - AWS S3, MinIO, or compatible

---

## Support

### Documentation

All documentation is in the `docs/` directory, organized by topic.

### Issues

- Check [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for common problems
- Review existing GitHub issues
- Create new issue with detailed description

### External Resources

- [Supabase Documentation](https://supabase.com/docs)
- [PostgREST API Reference](https://postgrest.org/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [PostGIS Documentation](https://postgis.net/)

### Contact

University of Freiburg, Department of Forest Sciences

---

## License

[Specify your license here]

---

**Built with Supabase | PostgreSQL | PostGIS | Docker | Deno | Kong**
