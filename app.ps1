# PowerShell script for running commands in the app container

# Check if arguments are provided
if ($args.Count -eq 0) {
    # No arguments provided, open a shell
    docker-compose exec app bash
} else {
    # Pass all arguments to the container
    $commandArgs = $args -join ' '
    docker-compose exec app $commandArgs
} 