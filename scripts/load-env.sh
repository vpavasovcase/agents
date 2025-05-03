#!/bin/bash

# Script to load environment variables from .env file
# and export them to the container environment

# Check if .env file exists
if [ -f .env ]; then
  echo "Loading environment variables from .env file..."
  
  # Read each line from .env file
  while IFS= read -r line || [ -n "$line" ]; do
    # Skip comments and empty lines
    if [[ ! "$line" =~ ^# && -n "$line" ]]; then
      # Extract variable name and value
      if [[ "$line" =~ ^([^=]+)=(.*)$ ]]; then
        var_name="${BASH_REMATCH[1]}"
        var_value="${BASH_REMATCH[2]}"
        
        # Remove quotes if present
        var_value="${var_value%\"}"
        var_value="${var_value#\"}"
        var_value="${var_value%\'}"
        var_value="${var_value#\'}"
        
        # Export the variable
        export "$var_name"="$var_value"
        echo "Exported: $var_name"
      fi
    fi
  done < .env
  
  echo "Environment variables loaded successfully."
else
  echo "Warning: .env file not found."
fi
