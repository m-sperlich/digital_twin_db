#!/bin/bash

# Supabase Key Generator (Docker-based)
# No Node.js installation required!
#
# Usage:
#   ./generate-keys.sh           # Display keys only
#   ./generate-keys.sh --write   # Automatically update .env file

set -e

echo "🔐 Supabase Key Generator - XR Future Forests Lab"
echo ""
echo "Using Docker to generate keys (no Node.js installation required)..."
echo ""

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo "❌ Error: Docker is not installed or not in PATH"
    echo "Please install Docker Desktop first: https://www.docker.com/products/docker-desktop/"
    exit 1
fi

# Get the root directory (parent of utils)
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# Run the Node.js script in a Docker container
docker run --rm -v "$ROOT_DIR:/app" -w /app node:18-alpine sh -c "
    npm install -g jsonwebtoken > /dev/null 2>&1 &&
    node utils/generate-keys.js $@
"
