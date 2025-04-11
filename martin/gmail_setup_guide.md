# Gmail API Setup Guide

This guide will help you set up the necessary credentials to use the Gmail API with the ClaudePost MCP server.

## Prerequisites

1. Python 3.7 or higher
2. Node.js and npm installed
3. A Google account

## Step 1: Set Up a Google Cloud Project

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Gmail API:
   - In the sidebar, navigate to "APIs & Services" > "Library"
   - Search for "Gmail API" and select it
   - Click "Enable"

## Step 2: Create OAuth 2.0 Credentials

1. In the Google Cloud Console, navigate to "APIs & Services" > "Credentials"
2. Click "Create Credentials" and select "OAuth client ID"
3. Select "Desktop app" as the application type
4. Enter a name for your OAuth client (e.g., "Gmail MCP Client")
5. Click "Create"
6. Download the credentials JSON file
7. Rename the downloaded file to `credentials.json` and place it in the same directory as your `run_gmail.py` script

## Step 3: Install Required Packages

The script will automatically install the required Python packages:
- google-auth
- google-auth-oauthlib
- google-api-python-client

And the required npm packages:
- @pydantic/mcp-run-python
- claude-post

## Step 4: Run the Script

1. Run the script:
   ```
   python run_gmail.py
   ```

2. The first time you run the script, it will open a browser window asking you to authorize the application to access your Gmail account. Follow the prompts to grant access.

3. After authorization, the script will save a `token.json` file in the current directory. This file contains your access tokens and will be used for subsequent runs.

## Using the Gmail Assistant

Once set up, you can interact with the assistant to:

1. Run Python code
2. Read emails from your Gmail account
3. Send emails through your Gmail account

Example commands:

- "Show me my latest 5 emails"
- "Send an email to example@example.com with the subject 'Test Email' and body 'This is a test email'"
- "Run a Python script to analyze my email data"

## Troubleshooting

- If you encounter authentication errors, delete the `token.json` file and run the script again to re-authenticate.
- Make sure your Google Cloud project has the Gmail API enabled.
- If you're having issues with the ClaudePost MCP server, try reinstalling it with `npm install -g claude-post`.