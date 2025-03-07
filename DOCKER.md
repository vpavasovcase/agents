# Docker Setup for Agents Project

This document provides instructions on how to use the Docker setup for the Agents project.

## Prerequisites

- Docker installed on your system
- Git (optional, for version control)

## Getting Started

1. Clone the repository (if you haven't already):
   ```bash
   git clone <repository-url>
   cd agents
   ```

2. Configure your environment variables:
   - Copy the `.env.docker` file and update it with your credentials:
     ```bash
     cp .env.docker .env.docker.local
     ```
   - Edit `.env.docker.local` and update the following variables:
     ```
     GITHUB_USER_NAME=your_github_username
     GITHUB_USER_EMAIL=your_github_email
     GITHUB_TOKEN=your_github_personal_access_token
     SUPABASE_URL=your_supabase_url
     SUPABASE_KEY=your_supabase_key
     ```
   - Rename your local file to be used by the sail script:
     ```bash
     mv .env.docker.local .env.docker
     ```

### GitHub Personal Access Token

To create a GitHub Personal Access Token:

1. Go to your GitHub account settings
2. Select "Developer settings" from the sidebar
3. Click on "Personal access tokens" and then "Tokens (classic)"
4. Click "Generate new token" and select "Generate new token (classic)"
5. Give your token a descriptive name
6. Select the scopes or permissions you'd like to grant this token
   - For most Git operations, you'll need at least `repo` scope
   - For private repositories, ensure you include the appropriate scopes
7. Click "Generate token"
8. Copy the token (you won't be able to see it again!)
9. Paste it into your `.env.docker` file as the `GITHUB_TOKEN` value

## Using the Sail Script

The `sail` script provides a convenient way to interact with the Docker container, similar to Laravel Sail.

### Basic Commands

- **Build the Docker image**:
  ```bash
  ./sail build
  ```

- **Start the container**:
  ```bash
  ./sail start
  ```

- **Stop the container**:
  ```bash
  ./sail stop
  ```

- **Restart the container**:
  ```bash
  ./sail restart
  ```

- **Enter the container shell**:
  ```bash
  ./sail shell
  ```

### Running Commands in the Container

- **Execute a command**:
  ```bash
  ./sail exec <command>
  ```
  Example:
  ```bash
  ./sail exec ls -la
  ```

- **Run Python**:
  ```bash
  ./sail python <script.py>
  ```
  Example:
  ```bash
  ./sail python -m your_module
  ```

- **Use pip**:
  ```bash
  ./sail pip install <package>
  ```

- **View container logs**:
  ```bash
  ./sail logs
  ```
  With options:
  ```bash
  ./sail logs --follow
  ```

## Docker Details

The Docker setup includes:

- Ubuntu 22.04 as the base image
- Git for version control
- Python 3 with pip
- Supabase CLI
- All Python dependencies from requirements.txt

### Entrypoint Script

The Docker container uses an entrypoint script (`docker-entrypoint.sh`) that:

1. Configures Git credentials from environment variables:
   - Sets `user.name` from `GITHUB_USER_NAME`
   - Sets `user.email` from `GITHUB_USER_EMAIL`

2. Configures GitHub token for authentication:
   - Sets up credential helper to use the token
   - Configures Git to use the token for GitHub operations
   - Secures the credentials file with appropriate permissions

3. Verifies Supabase credentials are available:
   - Checks for `SUPABASE_URL` and `SUPABASE_KEY`

This script runs automatically when the container starts, ensuring your credentials are properly configured.

## Customization

You can customize the Docker setup by:

1. Modifying the `Dockerfile` to include additional dependencies
2. Updating the `.env.docker` file to include additional environment variables
3. Extending the `sail` script with additional commands
4. Modifying the `docker-entrypoint.sh` script to perform additional setup tasks

## Troubleshooting

- If you encounter permission issues with the `sail` script or entrypoint script, make sure they're executable:
  ```bash
  chmod +x sail docker-entrypoint.sh
  ```

- If the container fails to start, check the Docker logs:
  ```bash
  docker logs agents-container
  ```

- If you need to rebuild the image after making changes to the Dockerfile:
  ```bash
  ./sail build
  ./sail restart
  ```

- If you're having issues with GitHub authentication:
  - Verify your token has the correct scopes
  - Check that the token is correctly set in the `.env.docker` file
  - Ensure the token hasn't expired (GitHub tokens can expire) 