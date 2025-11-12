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

# Build the keygen image if it doesn't exist
if ! docker images | grep -q "xr-forests-keygen"; then
    echo "Building key generator image (one-time setup)..."
    docker build -f "$ROOT_DIR/docker/Dockerfile.keygen" -t xr-forests-keygen "$ROOT_DIR"
    echo ""
fi

# Run the key generator as non-root user to avoid permission issues
# The Dockerfile uses UID 1000 which matches most Linux users
docker run --rm -v "$ROOT_DIR:/app" xr-forests-keygen $@
