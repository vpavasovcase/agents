#!/bin/bash

# Connect directly to PostgreSQL
if [ $# -eq 0 ]; then
    # No arguments provided, open psql interactive shell
    docker-compose exec postgres psql -U postgres
else
    # Pass all arguments to psql
    docker-compose exec postgres psql -U postgres "$@"
fi 