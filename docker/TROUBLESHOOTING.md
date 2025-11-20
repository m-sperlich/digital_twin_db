# Troubleshooting Guide

## Error: "password authentication failed for user supabase_admin"

This error occurs when the database was previously initialized with a different password than what's currently in your `.env` file.

### Solution: Complete Reset

```bash
cd docker

# Stop all containers and remove volumes
docker compose down -v --remove-orphans

# Clean up the database data directory
sudo rm -rf ./volumes/db/data

# Start fresh
docker compose up
```

### Why This Happens

PostgreSQL users and passwords are set during initial database creation. Changing `POSTGRES_PASSWORD` in `.env` after the database is already initialized doesn't update existing users.

The `-v` flag removes **all** volumes, and deleting `volumes/db/data` ensures a completely fresh start.

### Alternative: Using the Helper Scripts

**Option 1: Use reset.sh (resets .env from .env.example)**
```bash
cd docker
./reset.sh
# This will ask for confirmation and:
# - Remove all containers and volumes
# - Clean up database data
# - Copy .env.example to .env (ready to use immediately)
```

**Option 2: Use cleanup-volumes.sh (keeps .env)**
```bash
cd docker
./cleanup-volumes.sh
docker compose up
```

---

## Error: "database _supabase does not exist"

This was caused by missing `POSTGRES_USER` environment variable. This has been fixed in the latest `.env` file.

### Solution

Pull the latest changes and reset:
```bash
git pull
cd docker
docker compose down -v --remove-orphans
docker compose up
```

---

## Permission Issues with volumes/db/data

The `volumes/db/data` directory is owned by UID 105 (postgres user inside container). This is **expected and correct**.

### Solution

1. **Add yourself to docker group** (one-time setup):
   ```bash
   sudo usermod -aG docker $USER
   # Log out and back in
   ```

2. **Don't manually edit files** in `volumes/db/data` - let Docker manage it

3. **Use docker commands** to manage volumes:
   ```bash
   docker compose down -v    # Remove volumes
   ./cleanup-volumes.sh      # Clean with proper permissions
   ```

---

## Services Not Starting / Unhealthy

Check the status of all services:
```bash
cd docker
docker compose ps
```

Check logs for a specific service:
```bash
docker logs dftdb-db          # Database logs
docker logs dftdb-analytics   # Analytics logs
docker logs dftdb-auth        # Auth logs
```

Start a specific service manually:
```bash
docker compose start <service-name>
```

---

## Best Practices

1. **Always use `docker compose down -v`** when resetting to ensure volumes are removed
2. **Pull latest changes** before starting if working with others
3. **Don't commit `.env`** - it's gitignored for a reason
4. **Use `.env.example`** as a reference for what values should look like
5. **For local development**, the current secrets are fine (not production-ready)
