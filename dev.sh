#!/bin/bash

# Print colorful status messages
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Starting Docker services...${NC}"
docker-compose up -d

# Check if docker-compose up was successful
if [ $? -ne 0 ]; then
    echo -e "${YELLOW}Error starting Docker services. Exiting.${NC}"
    exit 1
fi

echo -e "${GREEN}Docker services started successfully!${NC}"

# Define aliases for container access
# Note: These aliases only work when you source this script with `. ./dev.sh` or `source ./dev.sh`
alias app="docker-compose exec app"
alias db="docker-compose exec postgres"
alias psql="docker-compose exec postgres psql -U postgres"

# Print usage information
echo -e "${GREEN}=== Development Environment Ready ===${NC}"
echo -e "The following aliases are now available in this terminal session:"
echo -e "${YELLOW}app${NC}   - Run commands in the application container (e.g., app python -m my_script)"
echo -e "${YELLOW}db${NC}    - Run commands in the PostgreSQL container (e.g., db bash)"
echo -e "${YELLOW}psql${NC}  - Connect directly to PostgreSQL (shortcut for 'db psql -U postgres')"
echo -e ""
echo -e "${YELLOW}Important:${NC} These aliases only work in this terminal session."
echo -e "To use these aliases, you must source this script using:"
echo -e "  ${YELLOW}source ./dev.sh${NC} or ${YELLOW}. ./dev.sh${NC}"
echo -e ""
echo -e "If you ran this with ${YELLOW}bash ./dev.sh${NC}, the aliases won't be available."

# Make the script usable for both direct execution and sourcing
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    echo -e "${YELLOW}Note: You executed this script directly.${NC}"
    echo -e "To use the aliases, please run: ${YELLOW}source ./dev.sh${NC} instead."
fi 