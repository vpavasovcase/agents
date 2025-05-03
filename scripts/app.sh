#!/bin/bash

# Check if any arguments were provided
if [ $# -eq 0 ]; then
  # No arguments, open a bash shell in the app container
  docker-compose exec app bash
else
  # Arguments provided, run the command in the app container
  docker-compose exec app "$@"
fi
