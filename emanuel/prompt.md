# Task

We are building an AI agent that automates the process of filling out a loan agreement template. The agent will be able to extract data from a couple of credit application documents, validate the data, and fill out the template. The agent will be able to handle missing data by asking the user for the missing information. The agent will be able to handle errors by asking the user to confirm the data. The agent will be able to handle multiple languages.

## Workflow

We will need multiple agents for this. The workflow is as follows:

1. The user provides the credit number in the CLI loop.
2. The documents are in the `docs/sources/<credit>` folder. The provided documents are in various forms, some are PDF with text, but some are PDF with image of the scanned documents. We need to convert the PDFs to image, then do the OCR. We will use `pdf2image` and `pytesseract` for this. Let's name this agent Read Agent. He will save the extracted text from all of the documents in a variable called `extracted_text`. When the Read Agent is finished, he will call Analysis Agent. Use server-filesystem MCP server for accessing the files.
3.  Analysis Agent will analyze the template which is in the `docs/template.docx` file and extract fileds which have to be filled out. He will save the fields in a variable `required_fields` and call the Search Agent. He will also analyze the `docs/template.pdf` which has some comments that can help him better understand the context of the fields, and when he does, he will check if `required_fields` are correcly formed. `required_fields` will contain the strings from the `docs/template.docx` that need to be replaced with actual values.
4. The Search Agent will then loop over `required_fields` and search for the data in the `extracted_text`. If the data is found, he will save it in a variable called `found_data` which will be a dictionary with `required_fields` as keys and the found data as values. If the data is not found or is ambiguous and requires users decision, he will save the field in a variable called `missing_data`. When he is finished, he will call the Ask Agent.
5. The Ask Agent will ask the user for the `missing_data` one by one. He will formulate each question in a way that allows the user to understand the context of the question. When he gets an answer, he will add it to found_data. When all `missing_data` is found, he will call the Fill Agent.
6. The Fill Agent will then make a copy of the `docs/template.docx` file into `docs/completed` folder, named as the credit number, e.g. `3254563456345.docx`. He will then replace the strings from keys from `found_data` with corresponding values from `found_data`. When he is finished, he will call the Final Agent. Use office-word-mcp-server for accessing the Word documents.
7. The Final Agent will then validate the filled out template and check if the filled document makes sense. If there are any errors, he will decide if he should loop back to any of the other agents and repeat the process; OR inform the user what the problem seems to be. If there are no errors, he will inform the user the task is finished and hive him the path to the filled document.

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

https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem
https://github.com/GongRzhe/Office-Word-MCP-Server
```
mcp_servers = [
    MCPServerStdio("npx", ["-y", "@modelcontextprotocol/server-filesystem", DOCS_BASE_PATH]),
    MCPServerStdio("uvx", ["--from", "office-word-mcp-server", "word_mcp_server"]),
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
- when planning the app, YOU MUST consult PydanticAI docs at https://ai.pydantic.dev/ and all the other docs mentioned in the prompt. don't use your training data, use the current docs.
- think about the workflow in this prompt and see if it makes sense and if you can improve it.
- keep going until the job is completed.
- if you are unsure about something, don't halucinate, resarch it online first and if you can't find the answer, ask me.
- plan thouroghly before any tool call, and reflect on the result after.