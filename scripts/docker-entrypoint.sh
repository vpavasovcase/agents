#!/bin/bash

# Docker entrypoint script
# This script runs when the container starts

# Load environment variables from .env file
if [ -f /app/scripts/load-env.sh ]; then
  echo "Running load-env.sh script..."
  source /app/scripts/load-env.sh
fi

# Install Python dependencies
if [ -f /app/scripts/install-dependencies.sh ]; then
  echo "Running install-dependencies.sh script..."
  source /app/scripts/install-dependencies.sh
fi

# Execute the command passed to docker run
exec "$@"
