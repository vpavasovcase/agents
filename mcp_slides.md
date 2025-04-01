Okay, here are the presentation slides for a 90-minute lecture on PydanticAI and its integration with the Model Context Protocol (MCP), based on the provided documentation.

---

**Slide 1: Title Slide**

**PydanticAI & the Model Context Protocol (MCP)**

Leveraging External Tools and Services Seamlessly

(Your Name/Affiliation)  
(Date - e.g., April 1, 2025)

---

**Slide 2: What is Model Context Protocol (MCP)?**

* **Standardized Protocol:** Defines how AI applications (agents, IDEs, desktop apps) connect to external tools/services.  
* **Goal:** Interoperability. Allow diverse clients to use diverse tools without specific integrations.  
* **Analogy:** Think HTTP for web browsers/servers, but for AI tools.  
* **Resource:** [modelcontextprotocol.io](https://modelcontextprotocol.io)  
* **Server List:** [github.com/modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers)

---

**Slide 3: PydanticAI + MCP Integration**

PydanticAI interacts with MCP in three key ways:

1. **MCP Client:** Agent can connect to external MCP servers to use their tools.  
2. **Inside MCP Servers:** Agent can be embedded within custom MCP server tools.  
3. **MCP Server Provider:** PydanticAI develops and provides its own MCP servers (e.g., Run Python).

---

**Slide 4: PydanticAI as an MCP Client**

* **Purpose:** Enables PydanticAI Agent instances to utilize capabilities offered by external MCP tool servers.  
* **Example Use Cases:**  
  * Web search via a search server.  
  * Log analysis via a logging server (e.g., Logfire).  
  * Running sandboxed code via a code execution server.

---

**Slide 5: Client Installation**

* Requires pydantic-ai or pydantic-ai-slim with the mcp extra.  
* Python 3.10+ is needed for MCP integration.

```Bash

# Using pip  
pip install "pydantic-ai-slim[mcp]"  
# or  
pip install "pydantic-ai[mcp]"

# Using uv  
uv pip install "pydantic-ai-slim[mcp]"  
# or  
uv pip install "pydantic-ai[mcp]"
```
---

**Slide 6: Connecting via HTTP SSE (MCPServerHTTP)**

* Connects to an MCP server over HTTP using Server-Sent Events (SSE).  
* Specified Transport: [HTTP + SSE](https://spec.modelcontextprotocol.io/specification/2024-11-05/basic/transports/#http-with-sse)  
* **Requirement:** The target MCP server must be running *before* the client attempts to connect. PydanticAI does *not* manage the server lifecycle here.

---

**Slide 7: SSE Client Example**

* Uses mcp-run-python server (must be started separately).

```Bash

npx @pydantic/mcp-run-python sse  
# Server listens on http://localhost:3001/sse by default
```
```Python

import asyncio  
from pydantic_ai import Agent  
from pydantic_ai.mcp import MCPServerHTTP

# 1. Define the server connection  
server = MCPServerHTTP(url='http://localhost:3001/sse')

# 2. Create Agent with the server  
agent = Agent('openai:gpt-4o', mcp_servers=[server])

async def main():  
    # 3. Manage the client session  
    async with agent.run_mcp_servers():  
        result = await agent.run(  
            'How many days between 2000-01-01 and 2025-03-18?'  
        )  
    print(result.data)  
    # Output: There are 9,208 days between January 1, 2000, ...

if __name__ == "__main__":  
    asyncio.run(main())
```
---

**Slide 8: How the SSE Client Interaction Works**

1. **Prompt:** Agent receives the user's prompt (e.g., "days between dates").  
2. **Tool Selection:** The LLM identifies an available tool from the MCP server (e.g., run_python_code) suitable for the task.  
3. **Tool Call Generation:** The LLM generates the parameters for the tool (e.g., the Python code to calculate the date difference).  
4. **Transmission:** PydanticAI sends the tool call request to the MCP server via HTTP SSE.  
5. **Execution:** The MCP server executes the tool (runs the Python code).  
6. **Response:** The MCP server sends the result back to PydanticAI.  
7. **Final Answer Generation:** PydanticAI provides the tool result back to the LLM, which generates the final natural language response.

*(Can be visualized with tools like Logfire)*

---

**Slide 9: Connecting via Stdio (MCPServerStdio)**

* Runs the MCP server as a **subprocess**.  
* Communication occurs over the subprocess's stdin and stdout.  
* Specified Transport: [stdio](https://spec.modelcontextprotocol.io/specification/2024-11-05/basic/transports/#stdio)  
* **Lifecycle Management:** PydanticAI's agent.run_mcp_servers() context manager **starts and stops** the subprocess automatically.

---

**Slide 10: Stdio Client Example**

* Uses mcp-run-python server (started as subprocess).

```Python

import asyncio  
from pydantic_ai import Agent  
from pydantic_ai.mcp import MCPServerStdio

# 1. Define how to start the server subprocess  
server = MCPServerStdio('npx', ['-y', '@pydantic/mcp-run-python', 'stdio'])

# 2. Create Agent with the server  
agent = Agent('openai:gpt-4o', mcp_servers=[server])

async def main():  
    # 3. Context manager starts/stops the subprocess  
    async with agent.run_mcp_servers():  
        result = await agent.run(  
            'How many days between 2000-01-01 and 2025-03-18?'  
        )  
    print(result.data)  
    # Output: There are 9,208 days between January 1, 2000, ...

if __name__ == "__main__":  
    asyncio.run(main())
```
---

**Slide 11: PydanticAI's MCP Server: Run Python**

* **Package:** @pydantic/mcp-run-python (NPM)  
* **Purpose:** An MCP server providing a tool to execute arbitrary Python code.  
* **Core Technology:** Uses [Pyodide](https://pyodide.org/) (Python compiled to WebAssembly).  
* **Key Benefit:** Secure, sandboxed execution isolated from the host system.

---

**Slide 12: Run Python Server: Features**

* **Secure Execution:** Code runs in a WASM sandbox.  
* **Package Management:** Auto-detects import statements or uses inline metadata (# /// script) to install dependencies (via micropip).  
* **Complete Results:** Captures stdout, stderr, return values, and execution status.  
* **Async Support:** Handles async Python code correctly.  
* **Error Handling:** Provides detailed tracebacks on failure.

---

**Slide 13: Running the Run Python Server**

* Distributed via NPM, easily run with npx.  
* Choose the transport method:

```Bash

# For use with MCPServerStdio (subprocess)  
npx @pydantic/mcp-run-python stdio
```
```Bash

# For use with MCPServerHTTP (network)  
# Listens on http://localhost:3001/sse by default  
npx @pydantic/mcp-run-python sse
```
---

**Slide 14: Using Run Python with PydanticAI (Recap)**

* We've already seen how pydantic-ai Agent uses this server.  
* **SSE:** Start npx ... sse, then use MCPServerHTTP in Python.  
* **Stdio:** Use MCPServerStdio in Python, pointing to the npx ... stdio command. The agent manages the process.

The LLM decides when calculation is needed and generates Python code for the run_python_code tool provided by this server.

---

**Slide 15: Run Python Server: Direct Usage**

* Can be used by *any* MCP client, not just PydanticAI.  
* Example using the official mcp Python client library.

```Python

import asyncio  
from mcp import ClientSession, StdioServerParameters  
from mcp.client.stdio import stdio_client

code = """  
import numpy  
a = numpy.array([1, 2, 3])  
print(f"My array: {a}") # Example with print  
a # Return value  
"""

async def main():  
    server_params = StdioServerParameters(  
        command='npx', args=['-y', '@pydantic/mcp-run-python', 'stdio']  
    )  
    async with stdio_client(server_params) as (read, write):  
        async with ClientSession(read, write) as session:  
            await session.initialize()  
            tools = await session.list_tools()  
            print(f"Tool Name: {tools.tools[0].name}") # 'run_python_code'

            result = await session.call_tool('run_python_code', {'python_code': code})

            # Result is structured XML/text containing status, output, etc.  
            print("n--- MCP Tool Result ---")  
            print(result.content[0].text)

if __name__ == "__main__":  
    asyncio.run(main())
```
---

**Slide 16: Run Python Server: Dependency Management**

How does the server know which packages (like numpy or pydantic) to install?

1. **Inferred from Imports (Default):**  
   * Scans the python_code for import statements (e.g., import numpy).  
   * Attempts to install the detected packages using micropip.  
2. **Inline Script Metadata (PEP 723):**  
   * More explicit and preferred for clarity or when imports are indirect.  
   * Uses a special comment block at the start of the code.  
   * Allows version pinning (for non-binary packages).

---

**Slide 17: Run Python Server: Inline Metadata Example**

* Uses PEP 723 style comments to declare dependencies.

```Python

import asyncio  
from mcp import ClientSession, StdioServerParameters  
from mcp.client.stdio import stdio_client

# Note the special comment block defining dependencies  
code = """  
# /// script  
# dependencies = ["pydantic<3", "email-validator"]  
# ///  
import pydantic

class Model(pydantic.BaseModel):  
    email: pydantic.EmailStr

m = Model(email='hello@pydantic.dev')  
print(f"Validated: {m.email}")  
"""

async def main():  
    # ... (stdio_client setup as before) ...  
    server_params = StdioServerParameters(  
        command='npx', args=['-y', '@pydantic/mcp-run-python', 'stdio']  
    )  
    async with stdio_client(server_params) as (read, write):  
        async with ClientSession(read, write) as session:  
            await session.initialize()  
            result = await session.call_tool('run_python_code', {'python_code': code})  
            print(result.content[0].text) # Includes status and detected dependencies

if __name__ == "__main__":  
    asyncio.run(main())
```
---

**Slide 18: Run Python Server: Logging**

* The server *can* emit stdout and stderr from the executed Python code as MCP logging messages.  
* **Requires:** The client must request a specific logging level during the session initialization. Default is emergency (effectively off).  
* **Current Status:** Demonstrating this is currently difficult due to a limitation in the mcp Python client library's handling of log levels during connection ([python-sdk#201](https://github.com/modelcontextprotocol/python-sdk/issues/201#issuecomment-2727663121)).

---

**Slide 19: PydanticAI within an MCP Server**

* The flip side: Embed a PydanticAI Agent *inside* a tool offered by your *own* custom MCP server.  
* Allows leveraging LLM capabilities (reasoning, generation, specific instructions) as part of a tool's logic.  
* Example: Create an MCP tool that uses an Agent configured with a specific system prompt.

---

**Slide 20: Server Example: PydanticAI Tool**

* Uses mcp.server.fastmcp to build a simple MCP server.  
* Defines a poet tool that internally uses a PydanticAI Agent.

```Python

from mcp.server.fastmcp import FastMCP  
from pydantic_ai import Agent

# Create the MCP Server instance  
server = FastMCP('PydanticAI Poet Server')

# Configure an Agent to be used internally by the tool  
server_agent = Agent(  
    'anthropic:claude-3-5-haiku-latest', # Or your preferred model  
    system_prompt='Always reply in rhyme. Be concise.'  
)

# Define an MCP tool  
@server.tool()  
async def poet(theme: str) -> str:  
    """Generates a short rhyming poem about a given theme."""  
    print(f"Poet tool called with theme: {theme}")  
    # Use the Agent within the tool implementation  
    response = await server_agent.run(f'write a short poem about {theme}')  
    return response.data # Return the text result

if __name__ == '__main__':  
    # Run the MCP server (listens on stdio by default)  
    print("Starting PydanticAI Poet MCP Server on stdio...")  
    server.run()
```
---

**Slide 21: Client Example: Querying the Server**

* Connects to the custom mcp_server_with_agent.py using the mcp client library.

```Python

import asyncio  
import os  
import sys  
from mcp import ClientSession, StdioServerParameters  
from mcp.client.stdio import stdio_client

async def client():  
    # Command to run the server script using the current Python environment  
    server_params = StdioServerParameters(  
        command=sys.executable, # Use the same python interpreter  
        args=['mcp_server_with_agent.py'], # Path to the server script  
        env=os.environ # Pass environment variables (e.g., API keys)  
    )  
    print("Connecting to server...")  
    async with stdio_client(server_params) as (read, write):  
        async with ClientSession(read, write) as session:  
            await session.initialize()  
            print("Calling 'poet' tool for theme 'clouds'...")  
            result = await session.call_tool('poet', {'theme': 'clouds'})  
            print("n--- Poem Received ---")  
            print(result.content[0].text)  
            print("--------------------")

if __name__ == '__main__':  
    asyncio.run(client())
```
---

**Slide 22: Limitations & Future**

* **Sampling:**  
  * MCP defines a "sampling" mechanism where servers can request LLM completions *from the client*.  
  * PydanticAI (as a client) does not currently support fulfilling these sampling requests from servers.  
* **Ecosystem:** MCP is relatively new; the number of available servers and clients is growing.

---

**Slide 23: Summary & Q&A**

* **MCP:** Standardizes AI tool interactions.  
* **PydanticAI as Client:** Connects to MCP servers (SSE/Stdio) to use tools like run_python_code.  
  * Requires [mcp] extra install.  
  * Uses MCPServerHTTP or MCPServerStdio.  
* **Run Python Server:** PydanticAI's sandboxed Python execution server (@pydantic/mcp-run-python).  
* **PydanticAI in Servers:** Embed Agents within your custom MCP server tools.

**Questions?**

---

