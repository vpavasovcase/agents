Radimo ovog AI agenta. Molim te da napišeš kod za njega što spremniji da odmah radi.

# Traženje best buya
    Kada trebate kupiti nešto, zadate buđet i agent nađe najbolji proizvod za tu cijenu
**MVP**
- zadate kriterije koji su vam bitni kod proizvoda
- agent pretraži webshopove za najbolji proizvod za tu cijenu

    **Potrebni alati**
    - izvršavanje koda
    - memorija
    - web search i scraping  
## 1. Workflow
Za ovo ćeš trebati više agenata.

Ovako bi trebao ići proces:

1. pokreneš app i u terminalu upišeš šta želiš kupiti, ako je bitna lokacija ili vrijeme dostave, napišeš i to. npr: Hoću kupiti best buy bluetooth slušalice za android u hrvatskoj, imam 100 EUR.

2. agent za websearch pretraži web za dućane koji prodaju slušalice.

3. tu listu preda agentu za webcrawl koji nađe sve slušalice koje odgovaraju kriterijima i zapamti ih

4. kada završi, pokrene se agent za search koji nađe review o svakim slušalicama.

5. agent za webcrawl pregleda reviewe i odluči koje od slušalica su najbolje

6. korisnik dobije link na webshop sa najjeftinijim / najboljim za 100 EUR slušalicama

7. memorija se obriše
## 3. logging
Za pratiti šta rade agenti trebaš implementirati logiranje. Koristi Logfire:
https://ai.pydantic.dev/logfire/
  ```
  logfire.configure()
  Agent.instrument_all()
  ```
## 4. strukturiranje rezultata
Za svaki rezultat koji model vraća treba smisliti kako odgovor mora biti strukturiran i
validiran ako je moguće. to se radi s Pydantic ( ne PydanticAI ) klasama:
python
class cityLocation(BaseModel):
city: str
country: str
## 5. memorija
Agenti moraju imati mogućnost zapamtiti nađene proizvode i kasnije reviewe.
Predlažem da koristiš:
https://github.com/modelcontextprotocol/servers/tree/main/src/memory
## 6. agent za websearch
Ovo je agent za web search šta moraš razlikovat od agenta za crawl. Agent za web search samo dobije listu sajtova, a agent za crawl pročita svaki od tih sajtova i prati linkove na sajtu.

Agent ima dva zadatka:

    1. pretraži web za webshopove koji imaju tip proizvoda koji user traži, recimo max 10. kada dobiješ rezultate, loopaš kroz njih i svaki url sinkrono (run_sync) proslijedi agentu za crawl.

    2. nađe reviewe za svake slušalice i opet ih proslijedi agentu za crawl. to ćeš morat malo vidjet kako napravit tijek rada, da li u petlji sinkrono ili prvo spremit rezultate za svake slušalice. pogledaj karticu za memoriju, dokumentaciju za taj MCP, dakle imaš listu slušalica onda listu reviewa koji su u relaciji s jednim slušalicama. to ću dodatno pojasnit u videu, to je tzv. graf znanja, knowledge graph. a možeš i ti dodatno izguglat o tome.

## 7. agent za webcrawl

Ovaj agent je za pregledavat sajtove. Ima dva zadatka:

    1. pregledati svaki webshop, naći odgovarajuće proizvode na njima i zapisati to u memoriju. Svaki zapis o proizvodu (entity u knowledge graphu) bi trebao biti povezan ( relation u knowledge graphu) sa webshopom na kojem je nađen.
    2. za svaki proizvod pregledati reviewe i isto ih spremiti u memoriju povezane s proizvodom.
    https://github.com/mendableai/firecrawl-mcp-server?tab=readme-ov-file#running-on-cursor

## 8. agent za procjenu
kad svi drugi agenti završe svoje poslove, ovaj agent treba procijeniti koji je najbolji proizvod. za to ćeš morat smislit neki algoritam. možda pretvoriti reviewe u brojčanu ocjenu ako već nemaju ocjenu u reviewu.
Više o tome u docs: https://ai.pydantic.dev/output/

## Instructions
- the agent will be run from cli.
- make it in one python file if possible
- use PydanticAI for the agent, docs are here: https://ai.pydantic.dev/.
- use MCP servers for the tools where appropriate
- make a loop in which user can chat with the agent and ask for different products
- I am attaching docs and examples, check them out and write the code in that style

## MCP servers - real config:
```
mcp_servers = [
    MCPServerStdio('npx', ['-y', "@modelcontextprotocol/server-memory"]),
    MCPServerStdio('npx', ["-y", "firecrawl-mcp"], {
        "FIRECRAWL_API_KEY": os.getenv('FIRECRAWL_API_KEY') or ""
    }),
]
```

## Model
```
llm_model = GroqModel('meta-llama/llama-4-maverick-17b-128e-instruct', provider=GroqProvider(api_key=os.getenv('GROQ_API_KEY')))
```
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

