#!/bin/bash

# Run psql in the postgres container
if [ $# -eq 0 ]; then
  # No arguments, open an interactive psql shell
  docker-compose exec postgres psql -U postgres
else
  # Arguments provided, run psql with the arguments
  docker-compose exec postgres psql -U postgres "$@"
fi
