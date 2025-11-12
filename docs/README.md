# Documentation Index

This folder contains technical documentation for the XR Future Forests Lab database system.

---

## Getting Started

- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - Common issues and solutions
- **[SUPABASE_INTRO.md](SUPABASE_INTRO.md)** - Introduction to Supabase (what it is, how it works)
- **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** - Quick reference for daily use

---

## Architecture and Design

- **[architecture/architecture.md](architecture/architecture.md)** - System architecture overview
- **[architecture/database.md](architecture/database.md)** - Database schema design and ERD
- **[architecture/api.md](architecture/api.md)** - REST API endpoints and usage
- **[architecture/services.md](architecture/services.md)** - Service descriptions and ports
- **[architecture/data-contracts.md](architecture/data-contracts.md)** - Data contracts between services

---

## Deployment and Operations

- **[supabase/setup-guide.md](supabase/setup-guide.md)** - Production deployment guide
- **[tech-stack.md](tech-stack.md)** - Technology stack overview

---

## Reference

- **[reference/sources.md](reference/sources.md)** - Technical references and related tools

---

## Documentation Organization

### For New Team Members
Start with:
1. [../README.md](../README.md) - Project overview and setup instructions
2. [QUICK_REFERENCE.md](QUICK_REFERENCE.md) - Common commands

### For Developers
Explore:
- [architecture/database.md](architecture/database.md) - Database schema
- [architecture/api.md](architecture/api.md) - API endpoints
- [tech-stack.md](tech-stack.md) - Technologies used

### For Production Deployment
See:
- [supabase/setup-guide.md](supabase/setup-guide.md) - Server setup
- [architecture/services.md](architecture/services.md) - Service configuration

---

## File Structure

```
docs/
├── README.md                    # This file
├── QUICK_REFERENCE.md           # Quick reference guide
├── tech-stack.md                # Technology overview
│
├── architecture/                # System architecture
│   ├── architecture.md          # Overall system design
│   ├── database.md              # Database schema
│   ├── api.md                   # API documentation
│   ├── services.md              # Service descriptions
│   ├── data-contracts.md        # Inter-service contracts
│   └── xr_forests_complete_erd.dbml  # ERD diagram
│
├── supabase/                    # Deployment guides
│   └── setup-guide.md           # Production deployment
│
└── reference/                   # External references
    └── sources.md               # Technical resources
```

---

## Contributing to Documentation

When adding or updating documentation:

1. **Keep it concise** - Focus on what people need to know
2. **Use examples** - Include code snippets and commands
3. **Update the index** - Add new files to this README
4. **Test instructions** - Verify commands actually work
5. **Remove outdated content** - Keep docs current

---

**Last Updated**: November 2024
