# Setup Instructions For Windows Users

1. Install Docker: https://docs.docker.com/desktop/setup/install/windows-install

2. Clone the repo:
```powershell
git clone https://github.com/vpavasovcase/agents.git
cd agents
```

3. Make a .env file in the root of the repo:
```powershell
cp .env.example .env
```

4. Add your API keys to the .env file

## VS Code Development (Recommended)

1. Install VS Code and the "Dev Containers" extension
2. Open the project folder in VS Code
3. Press F1 (or Ctrl+Shift+P), type "Dev Containers: Reopen in Container" and select it
4. VS Code will restart and connect to your development container

Now you can:
- Edit code with full IntelliSense
- Debug with breakpoints
- Use the integrated terminal (automatically inside the container)
- Run Python files directly from VS Code

## Common Issues & Solutions

1. **Docker Desktop not starting?**
   - Make sure WSL2 is installed and enabled
   - Restart your computer after Docker installation

2. **Permission denied errors?**
   - Run PowerShell as Administrator
   - Or use: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

3. **VS Code can't find Python?**
   - Make sure you're inside the Dev Container (check bottom-left corner)
   - If needed, select Python interpreter: Press F1 -> "Python: Select Interpreter"

4. **Container not starting?**
   - Check if Docker Desktop is running
   - Try: `docker-compose down` then `docker-compose up -d`

## Important Notes

- You don't need Python or any other development tools on your computer - everything runs in Docker
- Required on your computer:
  - Docker Desktop
  - Git
  - VS Code with Dev Containers extension
  - Slack app
  - AnyDesk

- The Docker container runs Ubuntu Linux, so use Linux (Debian) commands in the container terminal, not Windows commands

- When using AI coding assistants, mention we're using a Docker development environment

## Need Help?

- Check the error message in the VS Code terminal
- Ask in the Slack channel
- Share your screen via AnyDesk if needed
