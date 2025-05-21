# Task

We ar building a complete, working, receipt processing agent.

## Workflow

User takes photos of receipts you want to enter into the database.
User copys these images to a folder within the repository, `noa/receipts`
The agent reads them, extracts the data you need, and saves it to the database.
After that, you can ask the agent to analyze your spending.

## logging
Use Logfire:
https://ai.pydantic.dev/logfire/
  ```
  logfire.configure()
  Agent.instrument_all()
  ```
## result structuring and validation
Use Pydantic ( not PydanticAI ) classes where appropriate:
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
    MCPServerStdio("npx", ["-y", "@modelcontextprotocol/server-filesystem", app/noa/receipts]),
    MCPServerStdio('npx', ['-y', '@pydantic/mcp-run-python', 'stdio']),
]
```

## Model
```
llm_model = GroqModel('meta-llama/llama-4-maverick-17b-128e-instruct', provider=GroqProvider(api_key=os.getenv('GROQ_API_KEY')))
```

## Loading Images
The agent will use filesystem MCP (https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem), you tell it: "save the receipts I uploaded today", it searches the folder for images copied today and loads them using this: https://ai.pydantic.dev/input/#image-input

## Working with the Database
See how to work with the database:
https://ai.pydantic.dev/examples/sql-gen/#example-code
Figure out which fields you'll need for receipts and create such a schema

## Spending Analysis
For this, give the agent the tool for writing and running Python code to perform analyses. That's the MCP we use in mcp/run_python.py, see there, and you also have it in the docs: https://ai.pydantic.dev/mcp/run-python/

For analysis, you can ask the agent whatever you need, for example, you ask: "how much did I spend on beers after school last month." The agent can calculate this based on when the receipts were issued and the items on them. And since you're talking to it in the terminal, it can also ask you for information it's missing for the analysis, in this case, when your school ends. Mention this in the system prompt, that it should ask the user if it's missing any data for analysis.

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
- make th app in foder noa
- the app will be run from cli.
- make it in one python file if possible
- use MCP servers for the tools where appropriate
- when planning the app, YOU MUST consult Pydantic AI docs at https://ai.pydantic.dev/ or Context7 mcp server and all the other docs mentioned in the prompt. don't use your training data, use the current docs. 
- make sure to follow Pydantic AI pattern, style and structure.