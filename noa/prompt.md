Radimo ovog AI agenta:

# Spremanje računa u bazu

    Agent pretvara slike računa u zapise u bazi

**MVP**
- želite pratiti i analizirati potrošnju, ili imati arhivu
- uslikate seriju računa, agent ih pročita i spremi u bazu podatke koje želite

    **Potrebni alati**
    - baza
    - filesystem
    - čitanje slika

## 1. Workflow
Mislim da je za ovo dovoljan jedan agent.
Slikaš račune koje hoćeš unesti u bazu.
Kopiraš te slike u neki folder unutar repozitorija, napravi novi u svom folderu
Agent ih pročita, izvadi podatke koje trebaš i spremi ih u bazu.
Nakon toga možeš pitati agenta da napravi analizu potrošnje.
## 3. logging
Za pratiti šta rade agenti trebaš implementirati logiranje. Koristi Logfire:
https://ai.pydantic.dev/logfire/
## 4. strukturiranje rezultata
Za svaki rezultat koji model vraća treba smisliti kako odgovor mora biti strukturiran i
validiran. to se radi s Pydantic ( ne PydanticAI) klasama:
```python
class cityLocation(BaseModel):
city: str
country: str
```
Više o tome u docs: https://ai.pydantic.dev/output/
## 5. učitavanje slika
Agent će koristiti filesystem MCP ( https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem ), kažeš mu: “spremi racune koje sam danas uploadao”, on pretraži folder za slike koje su danas kopirane i učita ih koristeći ovo: https://ai.pydantic.dev/input/#image-input
## 6. rad sa bazom
U ovom primjeru vidi kako raditi s bazom:
https://ai.pydantic.dev/examples/sql-gen/#example-code
Smisli koja polja će ti trebat za račune i napravi takvu shemu, kao što je u primjeru ovo:
DB_SCHEMA = """ CREATE TABLE records (     created_at timestamptz,     start_timestamp timestamptz,     end_timestamp timestamptz,     trace_id text,     span_id text,     parent_span_id text,     level log_level,     span_name text,     message text,     attributes_json_schema text,     attributes jsonb,     tags text[],     is_exception boolean,     otel_status_message text,     service_name text ); """

Baza se digne kad otvoriš docker container u vsc, a podaci za pristup bazi su ti u docker-compose.yml. To daj modelu koji koristiš kao assistenta za kodiranje, trebao bi znat iskodirat vezu s bazom
## 7. analiza potrošnje
za ovo daj agentu onaj alat za pisanje i pokretanje python koda da može radit analize. to je onaj MCP koji koristimo u mcp/run_python.py, vidi. tamo, a imaš i u docs:https://ai.pydantic.dev/mcp/run-python/

Za analizu možeš pitat agenta šta god trebaš, npr. pitaš ga: “koliko sam prošli mjesec potrošio na pive poslije škole.” Agent po vremenu kada su izdani računi i stavkama na njima može to izračunati. A pošto pričaš s njim u terminalu, može te i pitati informacije koje mu fale za analizu, u ovom slučaju kada ti završava škola. To mu spomeni u system promptu, da pita usera ako mu fali neki podatak za analizu.

## Instructions
- the agent will be run from cli.
- make it in one python file if possible
- use PydanticAI for the agent, docs are here: https://ai.pydantic.dev/.
- use MCP servers for the tools, here are some: https://github.com/modelcontextprotocol/servers

## Okolina

Radimo u ovom kontejneru:

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