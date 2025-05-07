# Docker Instructions

This repository has been dockerized to make it easy to run in any environment. The Docker image includes:

- Ubuntu 22.04 as the base image
- Python 3.11 (latest)
- pip and pipx
- uv and uvx
- Node.js and npm (which includes npx)
- Docker CLI
- All Python dependencies from requirements.txt
- Automatic loading of environment variables from .env file
- Automatic installation of Python dependencies on container startup

## Building the Docker Image

To build the Docker image locally, run:

```bash
docker build -t yourusername/repo-name:tag .
```

Replace `yourusername/repo-name:tag` with your preferred image name and tag.

## Running with Docker

### Using docker run

```bash
docker run -it --rm yourusername/repo-name:tag
```

### Using Docker Compose

For development with local files mounted:

```bash
docker-compose up -d
docker-compose exec app bash
```

This will start the container and give you a bash shell inside it, with your local files mounted at `/app`.

## Publishing to Docker Hub

1. Log in to Docker Hub:

```bash
docker login
```

2. Push the image:

```bash
docker push yourusername/repo-name:tag
```

## Using Docker-in-Docker

The Docker CLI is included in the image, and the Docker socket is mounted from the host when running with Docker Compose. This allows you to run Docker commands inside the container that interact with the host's Docker daemon.

## Notes

- The `.dockerignore` file excludes unnecessary files from the build context.
- The base image is Ubuntu 22.04, which provides a stable foundation.
- All dependencies are installed during the image build process, making it ready to use immediately.
- Python dependencies are also automatically installed when the container starts, ensuring they're always up-to-date.
- To customize the image further, modify the `Dockerfile` as needed.
- Environment variables from your `.env` file are automatically loaded when the container starts.
- The container uses a custom entrypoint script that sources the `.env` file and exports all variables to the container environment.


# Development Scripts Guide

This repository includes helper scripts to streamline your Docker-based development workflow. These scripts make it easy to start services and run commands in Docker containers without remembering long Docker commands.

## Available Scripts

There are two sets of scripts available:
- **Bash scripts** (`.sh`) for macOS and Linux users
- **PowerShell scripts** (`.ps1`) for Windows users

## For Windows Users

Install Docker: https://docs.docker.com/desktop/setup/install/windows-install/

If you didn't already, clone the repo:

```powershell
git clone https://github.com/vpavasovcase/agents.git
cd agents
```

If you're unable to run PowerShell scripts, you may need to adjust your execution policy:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Starting the Services
```powershell
docker-compose up -d
```
### Stoping the Services
```powershell
docker-compose down
```

### Working with the Application Container

```powershell
# Open a bash shell in the app container
.\scripts\app.ps1

# Run a specific command in the app container
.\scripts\app.ps1 python -m my_script.py

# Install a new Python package
.\scripts\app.ps1 pip install pandas
```

### Working with the Database Container

```powershell
# Open a bash shell in the PostgreSQL container
.\scripts\db.ps1

# Run a PostgreSQL backup command
.\scripts\db.ps1 pg_dump -U postgres > backup.sql
```

### Direct PostgreSQL Access

```powershell
# Open an interactive PostgreSQL shell
.\scripts\psql.ps1

# Run a specific SQL query
.\scripts\psql.ps1 -c "SELECT * FROM users;"

# Run a SQL file
.\scripts\psql.ps1 -f schema.sql
```
## For macOS and Linux Users

### Starting the Services

```bash
./scripts/start.sh
```

This script:
- Starts all Docker services defined in your `docker-compose.yml` file
- Runs in detached mode (`-d`)
- Provides status updates on the startup process

### Working with the Application Container

```bash
# Open a bash shell in the app container
./scripts/app.sh

# Run a specific command in the app container
./scripts/app.sh python -m my_script.py

# Install a new Python package
./scripts/app.sh pip install pandas
```

### Working with the Database Container

```bash
# Open a bash shell in the PostgreSQL container
./scripts/db.sh

# Run a PostgreSQL backup command
./scripts/db.sh pg_dump -U postgres > backup.sql
```

### Direct PostgreSQL Access

```bash
# Open an interactive PostgreSQL shell
./scripts/psql.sh

# Run a specific SQL query
./scripts/psql.sh -c "SELECT * FROM users;"

# Run a SQL file
./scripts/psql.sh -f schema.sql
```

## Execution Permissions

### On macOS/Linux

If you get a "permission denied" error, you may need to make the scripts executable:

```bash
chmod +x scripts/*.sh
```

### On Windows

If you're unable to run PowerShell scripts, you may need to adjust your execution policy:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

## Troubleshooting

### Docker Compose Not Running

If you see an error like "Connection refused" or "Container not running", make sure you've started the containers first:

```bash
./scripts/start.sh  # For macOS/Linux
.\scripts\start.ps1  # For Windows
```

### PowerShell Script Execution

If Windows displays security warnings, you may need to unblock the files:

```powershell
Get-ChildItem .\scripts\*.ps1 | Unblock-File
```

### Docker Not Installed

If you see "docker-compose: command not found", make sure Docker Desktop (or Docker Engine + Docker Compose) is installed and running on your system.