# AI Agent Development Workshop

This repository contains materials and student projects from a 20-hour AI agent development workshop focused on building practical AI agents using PydanticAI and the Model Context Protocol (MCP).

## Workshop Overview

The workshop was structured as a comprehensive introduction to AI agent development, combining theoretical foundations with hands-on project development:

- **Duration**: 20 hours total
- **Format**: Weekly 90-minute lectures followed by practical development
- **Framework**: [PydanticAI](https://ai.pydantic.dev/) - A Python agent framework for production-grade AI applications
- **Integration**: Model Context Protocol (MCP) for connecting agents to external tools and services

## Repository Structure

```
├── LECTURES.md          # Complete lecture materials and slides
├── MCP_LECTURE.md       # Specialized lecture on Model Context Protocol
├── STUDENT_PROJECTS.md  # Project ideas and requirements (Croatian)
├── STUDENT_PROJECTS_EN.md # Project ideas and requirements (English)
├── examples/            # Example agents and code snippets
├── exercises/           # Workshop exercises
├── snippets/            # Code snippets and utilities
├── mcp/                 # MCP server configurations
├── receipt-processor/   # Receipt processing agent (Noa's project)
├── document-filler/     # Document template population agent (Emanuel's project)
├── sponsor-finder/      # Sponsor finder agent (Martin's project)
├── social-promoter/     # Social media promotion agent (Marko's project)
└── sponsor-discovery/   # Enhanced sponsor discovery agent (Martin's advanced project)
```

## Lecture Topics Covered

### Core PydanticAI Concepts
- **Agent Architecture**: System prompts, tools, structured results, dependencies
- **Type Safety**: Using Python type hints for reliable AI applications
- **Dependency Injection**: Managing external resources and data sources
- **Error Handling**: Retries, validation, and robust error management

### Advanced Features
- **Dynamic System Prompts**: Context-aware agent behavior
- **Tool Integration**: Extending agent capabilities with external functions
- **Structured Responses**: Using Pydantic models for consistent outputs
- **Conversation Management**: Handling multi-turn interactions

### Integration & Deployment
- **Model Context Protocol (MCP)**: Connecting to external tools and services
- **Logfire Integration**: Real-time debugging and performance monitoring
- **Gradio Interfaces**: Creating web UIs for agent interaction
- **Production Considerations**: Best practices for deployment

## Student Projects

Five students each developed unique AI agents addressing real-world automation challenges:

### 1. **Receipt Processor** (`receipt-processor/`)
**Project**: Automated receipt data extraction and spending analysis
- Processes receipt images using OCR and LLM vision capabilities
- Extracts structured data (store, date, items, amounts)
- Stores data in PostgreSQL database
- Provides natural language spending analysis
- **Tech Stack**: Docker, PostgreSQL, Tesseract OCR, Groq API
- **Developer**: Noa

### 2. **Document Filler** (`document-filler/`)
**Project**: Automated document template filling from multiple sources
- Analyzes Word document templates to identify required fields
- Extracts data from multiple source documents (PDF, Excel, Word)
- Populates templates with extracted data
- **Focus**: Banking document automation
- **Tech Stack**: Custom MCP server for Office documents, OCR processing
- **Developer**: Emanuel

### 3. **Sponsor Finder** (`sponsor-finder/`)
**Project**: Automated sponsor outreach and management
- Searches web for potential sponsors based on criteria
- Generates personalized sponsorship inquiry emails
- Manages sponsor database and tracks responses
- **Tech Stack**: Gmail API, SQLite database, web scraping
- **Developer**: Martin

### 4. **Social Promoter** (`social-promoter/`)
**Project**: Automated social media campaign management
- Creates promotional content for products/services
- Schedules and publishes posts across platforms
- **Focus**: Consistent brand messaging and engagement
- **Developer**: Marko

### 5. **Sponsor Discovery** (`sponsor-discovery/`)
**Project**: Advanced sponsor finding with crawling capabilities
- Web crawling for sponsor discovery
- Memory system for tracking interactions
- Multi-agent architecture for search and outreach
- **Tech Stack**: Advanced web scraping, persistent memory
- **Developer**: Martin (advanced project)

## Key Technologies

- **[PydanticAI](https://ai.pydantic.dev/)**: Primary agent framework
- **[Model Context Protocol (MCP)](https://modelcontextprotocol.io)**: Tool integration standard
- **[Logfire](https://logfire.pydantic.dev/)**: Observability and debugging
- **[Gradio](https://gradio.app/)**: Web interface creation
- **Docker**: Containerization and deployment
- **PostgreSQL**: Database for structured data storage

## Getting Started

### Prerequisites
- Python 3.10+
- Docker and Docker Compose
- API keys for chosen LLM providers (OpenAI, Anthropic, Google, Groq)

### Basic Setup
1. Clone the repository:
   ```bash
   git clone https://github.com/vpavasovcase/agents.git
   cd agents
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

### Running Examples
Explore the `examples/` directory for basic agent implementations:

```bash
# Simple weather agent
python examples/weather_agent.py

# Bank support agent with tools
python examples/bank_support.py

# Library support agent
python examples/library_support_agent.py
```

## Project Ideas

The workshop identified several categories of useful AI agents:

### Automation Agents
- Social media management and promotion
- Document processing and data extraction
- Email outreach and follow-up management
- Receipt and expense tracking

### Discovery Agents
- Best deal finding across multiple platforms
- Sponsor and investor identification
- Market opportunity monitoring
- Price tracking and alerts

### Analysis Agents
- Spending pattern analysis
- Document comparison and validation
- Performance monitoring and reporting

## Learning Resources

- **LECTURES.md**: Complete workshop curriculum with code examples
- **MCP_LECTURE.md**: Deep dive into Model Context Protocol integration
- **examples/**: Working code examples for common patterns
- **snippets/**: Reusable code components and utilities

## Contributing

This repository serves as both educational material and a foundation for further development. Students and workshop participants are encouraged to:

1. Improve existing agents with new features
2. Add new example implementations
3. Share additional project ideas
4. Contribute to documentation and tutorials

## Workshop Philosophy

The workshop emphasized building **practical, useful agents** that solve real problems people face but avoid due to tedium. Each project focused on:

- **MVP Development**: Starting with minimum viable functionality
- **Iterative Improvement**: Building features incrementally
- **Real-world Application**: Solving actual user problems
- **Production Readiness**: Considering deployment and maintenance

## License

This project is open source and available under the MIT License.

## Acknowledgments

- **PydanticAI Team**: For creating an excellent agent development framework
- **Workshop Participants**: For their creativity and dedication in building practical solutions
- **Open Source Community**: For the tools and libraries that made this workshop possible