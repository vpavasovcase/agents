#!/bin/bash

# Run commands in the PostgreSQL container
if [ $# -eq 0 ]; then
    # No arguments provided, open a shell
    docker-compose exec postgres bash
else
    # Pass all arguments to the container
    docker-compose exec postgres "$@"
fi 