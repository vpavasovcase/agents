# Model Context Protocol & PydanticAI Framework
90-Minute Technical Lecture
---

# Agenda
- Problem space & motivation
- Model Context Protocol (MCP) overview
- PydanticAI framework introduction
- MCP integration in PydanticAI
- Practical examples & code walkthrough
- Hands-on exercise
- Q&A

---

# The Challenge
- AI models isolated from real-world data & tools
- Custom integrations creating fragmentation
- Scalability issues for connected AI systems
- "Information silos" limiting practical applications

---

# Model Context Protocol (MCP)
- Open standard introduced by Anthropic (Nov 2024)
- Unified method for AI to access contextual info
- Standardized execution of actions on external systems
- Solution for streamlined context management

---

# MCP: The "USB Port" for AI
- Universal interface for AI assistants
- Plug-and-play with diverse data sources & services
- No custom-built connections needed
- Simplifies development process
- Promotes interoperability across platforms

---

# MCP Key Objectives
- Universal access to arbitrary data sources
- Secure & standardized connections
- Sustainable ecosystem of reusable connectors
- Reduced development overhead

---

# MCP Architecture
- Client-server model
- Three primary roles:
  - Hosts
  - Clients
  - Servers

---

# MCP Components

| Component | Description | PydanticAI Example |
|-----------|-------------|-------------------|
| Hosts | Applications embedding AI models | Custom app using PydanticAI agent |
| Clients | LLM interfaces connecting to servers | PydanticAI Agent with mcp_servers |
| Servers | Expose data, tools & prompts | mcp-run-python server |
| Resources | Structured data LLMs can read | Data from external API via tool |
| Tools | External actions for execution | Python code execution via mcp-run-python |

---

# PydanticAI Overview
- Python agent framework by Pydantic team
- Brings FastAPI-like experience to AI development
- Model-agnostic (OpenAI, Anthropic, Gemini)
- Deep integration with Pydantic library

---

# PydanticAI Key Features
- Robust data validation & type safety
- Optional dependency injection system
- Structured responses using Pydantic models
- External system interaction via tools
- Integration with Pydantic Logfire for debugging
- Streamed responses with validation
- Graph support for complex workflows

---

# PydanticAI Building Blocks
- Agents
  - Central orchestrators
  - Interact with LLMs
  - Manage task flow
- Tools
  - Functions agents invoke
  - Perform specific actions
  - Retrieve external information
- Dependencies
  - Inject data/connections/logic at runtime
  - Enable context-aware behavior

---

# PydanticAI & MCP Integration
- PydanticAI agents as MCP clients
- Connect to any MCP-compliant server
- Access external capabilities via standardized interface
- Expanding potential with MCP ecosystem

---

# Connection Mechanisms
- MCPServerHTTP
  - Connections over HTTP using Server-Sent Events
  - External server running & accessible over network
- MCPServerStdio
  - Runs MCP server as subprocess
  - Communication via standard input/output
  - PydanticAI manages server lifecycle

---

# MCP-Run-Python Server
- Built within PydanticAI
- Executes arbitrary Python code
- Sandboxed environment (Pyodide)
- Key features:
  - Secure execution
  - Auto-detection of dependencies
  - Comprehensive output capture
  - Async code support
  - Detailed error reporting

---

# Code Example: HTTP Connection

```python
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerHTTP
import asyncio

async def main():
    server = MCPServerHTTP(url='http://localhost:8080')
    agent = Agent('openai:gpt-4', mcp_servers=[server])
    async with agent.run_mcp_servers():
        result = await agent.run("What is the current time?")
        print(result.data)

if __name__ == "__main__":
    asyncio.run(main())
```

---

# Code Example: Stdio Connection

```python
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerStdio
import asyncio

async def main():
    server = MCPServerStdio('npx', ['-y', '@pydantic/mcp-run-python', 'stdio'])
    agent = Agent('openai:gpt-4', mcp_servers=[server])
    async with agent.run_mcp_servers():
        result = await agent.run('Calculate 2 + 2 and print the result.')
        print(result.data) # Expected output: "4"

if __name__ == "__main__":
    asyncio.run(main())
```

---

# Hands-on Exercise
- Build simple PydanticAI agent with mcp-run-python
- Steps:
  1. Install: `pip install 'pydantic-ai-slim[mcp]'`
  2. Import necessary classes
  3. Create MCPServerStdio instance
  4. Define PydanticAI agent with server
  5. Take math expressions as input
  6. Send to mcp-run-python for execution
  7. Print results

---

# Common Challenges
- Context window limitations
- Maintaining context across interactions
- Ensuring relevant & accurate retrieval
- Security concerns with external connections
- When to use HTTP vs. Stdio

---

# MCPServerHTTP vs. MCPServerStdio
- Stdio
  - Convenient for local development
  - Works well with bundled servers like run-python
  - PydanticAI manages server lifecycle
- HTTP
  - Suitable for remote connections
  - Works with separately managed servers
  - Persistent connections via SSE

---

# Conclusion
- MCP addresses critical need in AI landscape
- Standardized framework for contextual AI
- PydanticAI's support makes it powerful framework
- mcp-run-python offers convenient extension capabilities

---

# Further Resources
- PydanticAI documentation: ai.pydantic.dev
- MCP specification & SDKs
- MCP servers repository: github.com/modelcontextprotocol/servers
- PydanticAI GitHub: github.com/pydantic/pydantic-ai

---

# Q&A
