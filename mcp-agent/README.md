# Pydantic AI MCP Agent Example

This repository demonstrates a basic implementation of a Pydantic AI agent that utilizes the Model Context Protocol (MCP) to access and execute tools. This example shows how to bridge the gap between MCP tools and Pydantic AI's agent framework.

NOTE that this is a very basic implementation. Over the next month I'll be expanding this in much more depth to make it fully conversational, add in easier management of MCP clients, support for multiple MCP clients, etc.

## Overview

The Model Context Protocol (MCP) is a standardized protocol for AI model interactions, allowing models to access external tools and context. This example demonstrates how to:

1. Connect to an MCP server
2. Convert MCP tools to Pydantic AI tools
3. Create an interactive agent that can use these tools

## How It Works

### Key Components

- **MCP Client**: Connects to an MCP server using stdio communication
- **Tool Conversion**: Transforms MCP tools into Pydantic AI compatible tools
- **Interactive Agent**: Provides a chat interface to interact with the AI agent

### File Structure

- `pydantic_mcp_agent.py`: Main application file that sets up the MCP client and runs the agent
- `mcp_tools.py`: Utility module that converts MCP tools to Pydantic AI tools
- `requirements.txt`: Dependencies required to run the application

## Code Explanation

### MCP Tools Conversion (`mcp_tools.py`)

The `mcp_tools.py` file contains the core functionality for converting MCP tools to Pydantic AI tools:

```python
async def mcp_tools(session: ClientSession) -> List[PydanticTool]:
    """Convert MCP tools to pydantic_ai Tools."""
    await session.initialize()
    tools = (await session.list_tools()).tools
    return [create_tool_instance(session, tool) for tool in tools]
```

This function:
1. Initializes the MCP session
2. Retrieves the list of available tools from the MCP server
3. Converts each MCP tool to a Pydantic AI tool

The `create_tool_instance` function handles the actual conversion:

```python
def create_tool_instance(session: ClientSession, tool: MCPTool) -> PydanticTool:
    """Initialize a Pydantic AI Tool from an MCP Tool."""
    async def execute_tool(**kwargs: Any) -> Any:
        return await session.call_tool(tool.name, arguments=kwargs)

    async def prepare_tool(ctx: RunContext, tool_def: ToolDefinition) -> ToolDefinition | None:
        tool_def.parameters_json_schema = tool.inputSchema
        return tool_def
    
    return PydanticTool(
        execute_tool,
        name=tool.name,
        description=tool.description or "",
        takes_ctx=False,
        prepare=prepare_tool
    )
```

This function:
1. Creates an execution function that calls the MCP tool
2. Creates a preparation function that sets up the tool's schema
3. Returns a Pydantic AI Tool with the appropriate configuration

### Agent Setup (`pydantic_mcp_agent.py`)

The main application file sets up the MCP client and initializes the agent:

```python
async def main() -> None:
    server_params = StdioServerParameters(
        command=os.getenv("NPX_COMMAND", "npx"),
        args=["-y", "@modelcontextprotocol/server-filesystem", str(pathlib.Path(__file__).parent)],
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            tools = await mcp_tools.mcp_tools(session)
            agent = Agent(model="openai:gpt-4o-mini", tools=tools)
            
            # Start the interactive chat loop
            await chat_loop(agent)
```

This function:
1. Configures the MCP server parameters
2. Establishes a connection to the MCP server
3. Converts MCP tools to Pydantic AI tools
4. Creates a Pydantic AI agent with the converted tools
5. Starts an interactive chat loop

## Getting Started

### Prerequisites

- Python 3.9+
- Node.js (for the MCP server)

### Installation

1. Clone this repository

2. Set up a virtual environment:
 
   **Windows:**
   ```
   python -m venv venv
   venv\Scripts\activate
   ```

   **macOS/Linux:**
   ```
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install the Python dependencies:
   ```
   pip install -r requirements.txt
   ```

### Running the Agent

1. Create a `.env` file with your OpenAI API key:
   ```
   OPENAI_API_KEY=your_api_key_here
   ```

2. Run the agent:
   ```
   python pydantic_mcp_agent.py
   ```

3. Interact with the agent through the command line interface

## How to Extend

You can extend this example by adding more MCP clients for the agent. I will be diving into this more myself soon!

## Dependencies

This example relies on the following key packages:
- `pydantic-ai`: Framework for building AI agents with Pydantic
- `mcp`: Model Context Protocol client library
- `openai`: OpenAI API client for accessing AI models

## Learn More

- [Model Context Protocol (MCP)](https://github.com/modelcontextprotocol/mcp)
- [Pydantic AI](https://github.com/pydantic/pydantic-ai)
