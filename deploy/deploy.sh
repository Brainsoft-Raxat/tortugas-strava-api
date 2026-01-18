#!/bin/bash
set -e

# Check if .env file exists
if [ ! -f .env ]; then
    echo "Error: .env file not found!"
    echo "Please create a .env file in the deploy/ directory before deploying."
    exit 1
fi

echo "Deploying Strava Platform..."

# Pull latest changes
git pull

# Rebuild and restart containers
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml build --no-cache
docker compose -f docker-compose.prod.yml up -d

echo "Deployment complete!"
echo ""
echo "Check status with:"
echo "  docker compose -f docker-compose.prod.yml ps"
echo ""
echo "View logs with:"
echo "  docker compose -f docker-compose.prod.yml logs -f app"
