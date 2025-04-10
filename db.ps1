# PowerShell script for running commands in the PostgreSQL container

# Check if arguments are provided
if ($args.Count -eq 0) {
    # No arguments provided, open a shell
    docker-compose exec postgres bash
} else {
    # Pass all arguments to the container
    $commandArgs = $args -join ' '
    docker-compose exec postgres $commandArgs
} 