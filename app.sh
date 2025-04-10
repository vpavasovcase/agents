#!/bin/bash

# Run commands in the app container
if [ $# -eq 0 ]; then
    # No arguments provided, open a shell
    docker-compose exec app bash
else
    # Pass all arguments to the container
    docker-compose exec app "$@"
fi 