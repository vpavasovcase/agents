import os
import asyncio
from dotenv import load_dotenv
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.mcp import MCPServerStdio
from pydantic_ai.providers.openai import OpenAIProvider

# Load environment variables from .env file
load_dotenv(override=True)

# --- Configuration ---

# 1. Configure MCP Servers for Tools
#    We need a web search tool for the MVP.
#    Using DuckDuckGo search via an MCP server.
#    Ensure you have npx/npm installed.
servers = [
    MCPServerStdio('npx', ['-y', '@modelcontextprotocol/server-search-duckduckgo', 'stdio']),
    # Add other servers here if needed later (e.g., email - though complex)
    # MCPServerStdio('npx', ['-y', '@pydantic/mcp-run-python', 'stdio']), # Python execution (optional for now)
]

# 2. Configure the Language Model
#    Using OpenAI GPT-4o as specified.
#    Requires OPENAI_API_KEY in your .env file.
openai_api_key = os.getenv('OPENAI_API_KEY')
if not openai_api_key:
    raise ValueError("Missing OPENAI_API_KEY in .env file or environment variables.")

model = OpenAIModel(
    'gpt-4o', # Or another model like 'gpt-3.5-turbo'
    provider=OpenAIProvider(api_key=openai_api_key)
)

# 3. Define the Agent
#    Give it a clear role and instructions via the system prompt.
system_prompt = """
You are an assistant specialized in finding potential sponsors for projects.
Your tasks are:
1. Receive a description of a project needing sponsorship.
2. Use the available web search tool (DuckDuckGo) to find companies or organizations that might be interested in sponsoring such a project based on their industry, previous activities, or stated values.
3. List the names of 3-5 potential sponsors you identified.
4. Draft a polite, professional, and concise email template that can be sent to these potential sponsors to inquire about sponsorship opportunities. The template should have placeholders for [Company Name] and [Your Project Name/Your Name].
Present the list of potential sponsors first, followed by the drafted email template.
"""

agent = Agent(
    model=model,
    system_prompt=system_prompt,
    mcp_servers=servers
)

# --- Main Execution Logic ---

async def main():
    print("=== Sponsor Finding Agent MVP ===")
    print("This agent will help find potential sponsors and draft an inquiry email.")
    print("=================================")

    # Get project description from the user
    project_description = input("\nPlease describe the project for which you need sponsorship:\n> ")

    if not project_description:
        print("Project description cannot be empty. Exiting.")
        return

    # Define the specific task for the agent based on user input
    user_task = f"""
    Find potential sponsors and draft an inquiry email for the following project:

    Project Description:
    "{project_description}"

    Remember to use the web search tool to find relevant companies and provide both the list of potential sponsors and the email draft.
    """

    print("\n[Agent] Searching for sponsors and drafting email... (This may take a moment)")

    # Run the MCP servers and the agent task
    async with agent.run_mcp_servers():
        try:
            # For this specific task, conversation history isn't crucial,
            # but we pass an empty list for consistency with the API.
            result = await agent.run(user_task, message_history=[])
            print("\n[Agent Result]")
            print("--------------")
            print(result.data) # Agent's response based on the system prompt and user task
            print("--------------")

        except Exception as e:
            print(f"\nError during agent execution: {e}")
            print("Please ensure:")
            print(" - Your OpenAI API key in .env is correct and has funds.")
            print(" - You have Node.js/npm/npx installed and accessible.")
            print(" - Your internet connection is stable.")

    print("\nAgent task completed.")

# --- Entry Point ---

if __name__ == '__main__':
    asyncio.run(main())