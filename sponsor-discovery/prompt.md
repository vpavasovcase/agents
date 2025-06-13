# Task

Build a complete, working, sponsor finding and email drafting agent.

## Workflow

1. Agent finds 20 websites for potential sponsors, based on the event user is organizing, for example if user is organizing bicicle race in Osijek, he will search for "bicicle shops in Osijek" and return 20 results.
2. Then the agent will loop throug that list of websites and for each website it will extract the name of the company, the email of the company, and the name of the contact person. He will then write the email asking for sponsorship and send it to gmail as a draft.

## logging
Use Logfire:
https://ai.pydantic.dev/logfire/
  ```
  logfire.configure()
  Agent.instrument_all()
  ```
## result structuring and validation
Use Pydantic ( not PydanticAI ) classes:
```python
class cityLocation(BaseModel):
city: str
country: str
```

## MCP servers
Check how to use MCP servers in the code: https://ai.pydantic.dev/mcp/client/#mcp-servers
When planning the app, check the docs for each of the required MCP servers:
```
mcp_servers = [
    MCPServerStdio('npx', ['-y', '@modelcontextprotocol/server-memory']),
    MCPServerStdio('npx', ['-y', '@mendableai/firecrawl-mcp-server']),
    MCPServerStdio('npx', ['-y', '@gongrzhe/gmail-mcp-server']),
]
```

## Model
```
llm_model = GroqModel('meta-llama/llama-4-maverick-17b-128e-instruct', provider=GroqProvider(api_key=os.getenv('GROQ_API_KEY')))
```
## Environment

docker-compose.yml:

```
version: '3.8'
services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
    volumes:
      - .:/app
      - /var/run/docker.sock:/var/run/docker.sock
    working_dir: /app
    stdin_open: true
    tty: true
    depends_on:
      - postgres
    env_file:
      - .env
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@postgres:5432/postgres
      - DATABASE_HOST=postgres
      - DATABASE_PORT=5432
      - DATABASE_USER=postgres
      - DATABASE_PASSWORD=postgres
      - DATABASE_NAME=postgres
  postgres:
    image: postgres:15
    environment:
      - POSTGRES_PASSWORD=postgres
      - POSTGRES_USER=postgres
      - POSTGRES_DB=postgres
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
volumes:
  postgres_data:
```

Dockerfile:
```
FROM ubuntu:22.04
# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC
# Install basic dependencies
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    git \
    software-properties-common \
    apt-transport-https \
    ca-certificates \
    gnupg \
    lsb-release \
    build-essential \
    && rm -rf /var/lib/apt/lists/*
# Install Python (latest)
RUN add-apt-repository ppa:deadsnakes/ppa -y \
    && apt-get update \
    && apt-get install -y python3.11 python3.11-venv python3.11-dev python3-pip \
    && ln -sf /usr/bin/python3.11 /usr/bin/python \
    && ln -sf /usr/bin/python3.11 /usr/bin/python3 \
    && rm -rf /var/lib/apt/lists/*
# Install pipx
RUN pip3 install --no-cache-dir pipx \
    && pipx ensurepath
# Install Node.js and npm (which includes npx)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*
# Install uv and uvx
RUN pip3 install --no-cache-dir uv \
    && pipx install uv \
    && ln -sf $(pipx environment --value PIPX_BIN_DIR)/uv /usr/local/bin/uvx
# Install Docker CLI
RUN curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
    $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null \
    && apt-get update \
    && apt-get install -y docker-ce docker-ce-cli containerd.io \
    && rm -rf /var/lib/apt/lists/*
# Set up working directory
WORKDIR /app
# Copy requirements.txt and install dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt
# Set PATH to include pipx installed binaries
ENV PATH="/root/.local/bin:$PATH"
# Copy scripts
COPY scripts/docker-entrypoint.sh /usr/local/bin/
COPY scripts/install-dependencies.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh /usr/local/bin/install-dependencies.sh
# Set entrypoint
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
# Set a default command
CMD ["/bin/bash"]
```

# Instructions
- the app will be run from cli.
- make it in one python file if possible
- use MCP servers for the tools where appropriate
- when planning the app, YOU MUST consult Pydantic AI docs at https://ai.pydantic.dev/ and all the other docs mentioned in the prompt. don't use your training data, use the current docs. 
- make sure to follow Pydantic AI pattern, style and structure.