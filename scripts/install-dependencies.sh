#!/bin/bash

# Script to install Python dependencies
echo "Checking for Python dependencies..."

# Check if requirements.txt exists
if [ -f /app/requirements.txt ]; then
  echo "Installing Python dependencies from requirements.txt..."
  pip3 install --no-cache-dir -r /app/requirements.txt
  echo "Python dependencies installed successfully."
else
  echo "Warning: requirements.txt not found."
fi

# Check if setup.py exists (for development mode installation)
if [ -f /app/setup.py ]; then
  echo "Installing package in development mode..."
  pip3 install -e /app
  echo "Package installed in development mode."
fi
