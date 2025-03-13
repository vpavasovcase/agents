#!/bin/bash
set -e

# Configure Git credentials if provided
if [ -n "$GITHUB_USER_NAME" ] && [ -n "$GITHUB_USER_EMAIL" ]; then
  git config --global user.name "$GITHUB_USER_NAME"
  git config --global user.email "$GITHUB_USER_EMAIL"
  echo "Git credentials configured."
fi

# Configure GitHub token if provided
if [ -n "$GITHUB_TOKEN" ]; then
  # Store GitHub token for HTTPS authentication
  git config --global credential.helper store
  echo "https://${GITHUB_TOKEN}:x-oauth-basic@github.com" > ~/.git-credentials
  chmod 600 ~/.git-credentials
  
  # Configure Git to use the token for GitHub operations
  git config --global url."https://${GITHUB_TOKEN}@github.com/".insteadOf "https://github.com/"
  
  echo "GitHub token configured."
fi

# Check for Supabase credentials
if [ -n "$SUPABASE_URL" ] && [ -n "$SUPABASE_KEY" ]; then
  echo "Supabase credentials available."
fi

# Execute the command passed to docker run
exec "$@" 