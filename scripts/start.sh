#!/bin/bash

# Start Docker services
echo "Starting Docker services..."
docker-compose up -d

echo "Services started successfully."
echo "You can now use the scripts/app.sh, scripts/db.sh, and scripts/psql.sh scripts to interact with the containers."
