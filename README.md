
# Development Scripts Guide

This repository includes helper scripts to streamline your Docker-based development workflow. These scripts make it easy to start services and run commands in Docker containers without remembering long Docker commands.

## Available Scripts

There are two sets of scripts available:
- **Bash scripts** (`.sh`) for macOS and Linux users
- **PowerShell scripts** (`.ps1`) for Windows users

## Setup Instructions For Windows Users

Install Docker: https://docs.docker.com/desktop/setup/install/windows-install

If you didn't already, clone the repo:

```powershell
git clone https://github.com/vpavasovcase/agents.git
cd agents
```

Make a .env file in the root of the repo:
```powershell
cp .env.example .env
```
Add API keys to the .env file.

### Starting the Services
```powershell
docker-compose up -d
```
### Stoping the Services
```powershell
docker-compose down
```

### Working with the Application Container

If you're unable to run PowerShell scripts, you may need to adjust your execution policy:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

```powershell
# Open a bash shell in the app container
.\app.ps1

# Run a specific command in the app container
.\app.ps1 python -m my_script.py

# Install a new Python package
.\app.ps1 pip install pandas
```

## Objasnjenje

Docker kontejner je kao da unutar svog kompa imate još jedan komp. Taj komp upalite sa:
```powershell
docker-compose up -d
```
a ugasite ga sa:
```powershell
docker-compose down
```


U terminalu radite sa svojim kompom kao inače, a da bi radili na docker kompu, morate:

1. ili pokenut terminal u docker kompu sa
    ```powershell
    .\app.ps1
    ```
    onda u tom terminalu pisati komandi koliko god želite, npr:     
    ```powershell
    python mcp/run_python.py
    python mcp/run.py
    pip install pandas
    ...
    ```
    Kada ste završili raditi na docker kompu, možete ga zatvoriti sa
    ```powershell
    exit
    ```
2. ili pokrenuti neku komandu direktno u docker kompu sa
    ```powershell
    .\app.ps1 python mcp/run_python.py
    ```
    U ovom slučaju ne ulazite u docker komp, nego samo pokrenete tu komandu u njemu ali ostajete u svom kompu.

## Napomene

- sada ne trebate pokretati venv
- sve šta nam treba je već instalirano na docker kompu:
    - python, git, pip, pipx, uv, uvx, node.js, docker (unutar docker kompa se isto mogu pokretati docker kontejneri)
- ako vam treba još nešto, javite mi pa instaliram
- vi na svom kompu ne trebate instalirati ništa osim dockera, slack appa i anydeska
