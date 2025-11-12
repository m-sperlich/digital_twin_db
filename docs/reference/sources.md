# Technical References and Resources

This document lists the key technologies, tools, and resources used in or relevant to the XR Future Forests Lab database implementation.

---

## Currently Implemented

### Database and Spatial Extensions

| Resource | Purpose | Documentation |
|----------|---------|---------------|
| [PostgreSQL 15](https://www.postgresql.org/) | Core relational database system | [Docs](https://www.postgresql.org/docs/15/) |
| [PostGIS](https://postgis.net/) | Spatial database extension for geographic data | [Docs](https://postgis.net/documentation/) |
| [Supabase](https://supabase.com/) | Open-source Firebase alternative providing database backend | [Docs](https://supabase.com/docs) |
| [PostgREST](https://postgrest.org/) | Automatic REST API generation from PostgreSQL schema | [Docs](https://postgrest.org/en/stable/) |

### API and Services

| Resource | Purpose | Documentation |
|----------|---------|---------------|
| [Kong API Gateway](https://konghq.com/) | API routing, authentication, and rate limiting | [Docs](https://docs.konghq.com/) |
| [GoTrue](https://github.com/netlify/gotrue) | User authentication and JWT management | [GitHub](https://github.com/netlify/gotrue) |
| [Deno](https://deno.land/) | Runtime for Edge Functions (serverless logic) | [Docs](https://deno.land/manual) |

### Storage and File Handling

| Resource | Purpose | Documentation |
|----------|---------|---------------|
| [AWS S3](https://aws.amazon.com/s3/) | Object storage for point cloud files (.las, .laz) | [Docs](https://docs.aws.amazon.com/s3/) |
| [Cloud Optimized Point Cloud (COPC)](https://copc.io/) | Efficient format for point cloud storage and streaming | [Spec](https://copc.io/) |

### Point Cloud Processing Tools

| Resource | Purpose | Integration Status |
|----------|---------|-------------------|
| [Potree](https://github.com/potree/potree) | Web-based point cloud renderer | Planned for visualization |
| [PDAL](https://pdal.io/) | Point cloud data processing library (C++/Python) | For external processing |
| [CloudCompare](https://www.cloudcompare.org/) | Point cloud and mesh processing software | Recommended tool |

---

## Planned Integrations

### Forest Growth Models

| Resource | Description | Integration Plan |
|----------|-------------|-----------------|
| [SILVA Model](https://www.optforests.eu/toolkit/models/silva) | Individual tree growth simulator used in European forestry | API integration for TreeSimulations table |
| [iLand](https://iland-model.org/) | Forest landscape dynamics model | Potential alternative growth model |

### Environmental Sensors

| Resource | Description | Integration Plan |
|----------|-------------|-----------------|
| [EcoSense](https://www.ecosense.uni-freiburg.de/) | Environmental sensor platform for forest monitoring | Data ingestion via API to sensor schema |

### Tree Modeling and Visualization

| Resource | Purpose | Integration Plan |
|----------|---------|-----------------|
| [The Grove 3D](https://www.thegrove3d.com/) | Blender add-on for procedural tree modeling | Generate 3D models from tree measurements |
| [glTF](https://github.com/KhronosGroup/glTF) | Open standard for 3D model transmission | Standard format for tree assets |
| [3D Tiles](https://github.com/CesiumGS/3d-tiles) | Specification for streaming massive 3D datasets | For XR visualization |

---

## Reference Libraries and Tools

### Point Cloud Analysis

| Resource | Description |
|----------|-------------|
| [3D Forest](https://www.3dforest.eu/) | Open-source tool for terrestrial LiDAR forest data segmentation |
| [lidR](https://github.com/ForestTools/lidR) | R package for airborne LiDAR data manipulation |
| [pytreedb](https://github.com/3dgeo-heidelberg/pytreedb) | Python library for single tree-based point cloud storage |

### Quantitative Structure Models (QSM)

| Resource | Description |
|----------|-------------|
| [SimpleForest](https://simpleforest.org/) | QSM generation from point clouds |
| [TreeQSM](https://github.com/InverseTampere/TreeQSM) | MATLAB tool for QSM reconstruction |
| [rTwig](https://aidanmorales.github.io/rTwig/) | R package for tree structure modeling |

### XR/VR Development

| Resource | Purpose |
|----------|---------|
| [Unity](https://unity.com/) | Real-time 3D development platform |
| [Unreal Engine](https://www.unrealengine.com/) | High-fidelity real-time 3D engine |
| [CesiumJS](https://cesium.com/platform/cesiumjs/) | Geospatial 3D visualization for the web |

### Scientific Computing

| Resource | Purpose |
|----------|---------|
| [NumPy](https://numpy.org/) | Scientific computing in Python |
| [pandas](https://pandas.pydata.org/) | Data analysis and manipulation |
| [Open3D](https://github.com/open3d/Open3D) | 3D data processing and ML |

---

## Standards and Best Practices

| Resource | Description |
|----------|-------------|
| [Digital Twin Consortium](https://www.digitaltwinconsortium.org/) | Industry standards and best practices for digital twins |
| [OGC SensorThings API](https://www.ogc.org/standards/sensorthings) | Open standard for sensor data exchange |
| [FAO Forest Information Model (FIM)](https://www.fao.org/3/ca7503en/ca7503en.pdf) | Standardized model for forest inventory data |

---

## Considered but Not Used

### OpenForis Collect

[OpenForis Collect](https://github.com/openforis/collect) provides a flexible schema for forest inventory data. While comprehensive, we opted for a custom schema tailored specifically to digital twin requirements with variant tracking, spatial integration, and XR visualization support.

**Key differences from our implementation**:
- OpenForis focuses on traditional forest inventory
- Our schema includes point cloud lineage, real-time sensor integration, and 3D asset management
- We use PostGIS spatial types instead of generic coordinates
- Our variant system supports multiple processing/simulation versions

### TimescaleDB

[TimescaleDB](https://www.timescale.com/) is a time-series database extension for PostgreSQL. We considered it for sensor data but opted for standard PostgreSQL with proper indexing on timestamps, which provides sufficient performance for our use case while reducing complexity.

### MongoDB and Neo4j

We evaluated NoSQL alternatives but chose PostgreSQL with PostGIS because:
- ACID compliance required for forest inventory data
- PostGIS provides superior spatial query capabilities
- Strong typing and schema validation
- Supabase ecosystem integration
- Team familiarity with SQL

---

## Contributing

If you're using tools or resources not listed here that could benefit the project, please:
1. Document the tool's purpose and use case
2. Provide integration examples or recommendations
3. Update this file with your findings

---

**Last Updated**: November 2024
