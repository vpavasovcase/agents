#!/usr/bin/env bash

# Define colors for output
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Define Docker image and container names
DOCKER_IMAGE="agents-app"
DOCKER_CONTAINER="agents-container"
ENV_FILE=".env.docker"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Docker is not installed. Please install Docker first.${NC}"
    exit 1
fi

# Function to build the Docker image
build() {
    echo -e "${GREEN}Building Docker image...${NC}"
    docker build -t ${DOCKER_IMAGE} .
    echo -e "${GREEN}Docker image built successfully!${NC}"
}

# Function to start the container
start() {
    if [ ! "$(docker ps -q -f name=${DOCKER_CONTAINER})" ]; then
        if [ "$(docker ps -aq -f status=exited -f name=${DOCKER_CONTAINER})" ]; then
            echo -e "${YELLOW}Removing existing stopped container...${NC}"
            docker rm ${DOCKER_CONTAINER}
        fi
        
        echo -e "${GREEN}Starting container...${NC}"
        docker run -d --name ${DOCKER_CONTAINER} \
            -v "$(pwd)":/app \
            --env-file ${ENV_FILE} \
            -p 8000:8000 \
            ${DOCKER_IMAGE}
        
        echo -e "${GREEN}Container started successfully!${NC}"
    else
        echo -e "${YELLOW}Container is already running.${NC}"
    fi
}

# Function to stop the container
stop() {
    if [ "$(docker ps -q -f name=${DOCKER_CONTAINER})" ]; then
        echo -e "${GREEN}Stopping container...${NC}"
        docker stop ${DOCKER_CONTAINER}
        echo -e "${GREEN}Container stopped successfully!${NC}"
    else
        echo -e "${YELLOW}Container is not running.${NC}"
    fi
}

# Function to restart the container
restart() {
    stop
    start
}

# Function to execute a command in the container
exec() {
    if [ "$(docker ps -q -f name=${DOCKER_CONTAINER})" ]; then
        docker exec -it ${DOCKER_CONTAINER} "$@"
    else
        echo -e "${RED}Container is not running. Start it first with './sail start'${NC}"
        exit 1
    fi
}

# Function to show container logs
logs() {
    if [ "$(docker ps -q -f name=${DOCKER_CONTAINER})" ]; then
        docker logs ${DOCKER_CONTAINER} "$@"
    else
        echo -e "${RED}Container is not running. Start it first with './sail start'${NC}"
        exit 1
    fi
}

# Function to enter the container shell
shell() {
    exec bash
}

# Function to run Python in the container
python() {
    exec python "$@"
}

# Function to run pip in the container
pip() {
    exec pip "$@"
}

# Function to display help
help() {
    echo -e "${GREEN}Agents Docker Helper Script${NC}"
    echo ""
    echo "Usage:"
    echo "  ./sail [command] [options]"
    echo ""
    echo "Available commands:"
    echo "  build                Build the Docker image"
    echo "  start                Start the container"
    echo "  stop                 Stop the container"
    echo "  restart              Restart the container"
    echo "  exec [command]       Execute a command in the container"
    echo "  logs [options]       View container logs"
    echo "  shell                Enter the container shell"
    echo "  python [options]     Run Python in the container"
    echo "  pip [options]        Run pip in the container"
    echo "  help                 Display this help message"
}

# Main script logic
if [ $# -eq 0 ]; then
    help
    exit 1
fi

case "$1" in
    build)
        build
        ;;
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    exec)
        shift
        exec "$@"
        ;;
    logs)
        shift
        logs "$@"
        ;;
    shell)
        shell
        ;;
    python)
        shift
        python "$@"
        ;;
    pip)
        shift
        pip "$@"
        ;;
    help)
        help
        ;;
    *)
        echo -e "${RED}Unknown command: $1${NC}"
        help
        exit 1
        ;;
esac

exit 0 