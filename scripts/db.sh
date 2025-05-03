#!/bin/bash

# Check if any arguments were provided
if [ $# -eq 0 ]; then
  # No arguments, open a bash shell in the postgres container
  docker-compose exec postgres bash
else
  # Arguments provided, run the command in the postgres container
  docker-compose exec postgres "$@"
fi
