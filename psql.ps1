# PowerShell script for connecting directly to PostgreSQL

# Check if arguments are provided
if ($args.Count -eq 0) {
    # No arguments provided, open psql interactive shell
    docker-compose exec postgres psql -U postgres
} else {
    # Pass all arguments to psql
    $commandArgs = $args -join ' '
    docker-compose exec postgres psql -U postgres $commandArgs
} 