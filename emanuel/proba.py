import asyncio
import os
import re
from dotenv import load_dotenv
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.mcp import MCPServerStdio
from pydantic_ai.providers.openai import OpenAIProvider

servers = [
    MCPServerStdio('npx', ['-y', '@pydantic/mcp-run-python', 'stdio']),
    MCPServerStdio('npx', [
              "-y",
              "@modelcontextprotocol/server-filesystem",
              "/app"
            ]),
]


# Load environment variables from .env file
load_dotenv(override=True)

# --- Configuration ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not found in .env file")

# Define the working directory for the filesystem server (use '.' for current directory)
# Ensure the user running the script has permissions in this directory
FILESYSTEM_WORKING_DIR = "." 

# --- MCP Server Setup ---
# We need a filesystem server and a python execution server
servers = [
    # Python execution server - allows running python code for complex tasks
    MCPServerStdio('npx', ['-y', '@pydantic/mcp-run-python', 'stdio']),
    # Filesystem server - for basic file listing, reading/writing text content if needed
    # Pointing it to the current directory allows relative paths
    MCPServerStdio('npx', ['-y', '@modelcontextprotocol/server-filesystem', FILESYSTEM_WORKING_DIR]) 
]

# --- LLM and Agent Setup ---
model = OpenAIModel('gpt-4o', provider=OpenAIProvider(api_key=OPENAI_API_KEY))

# Define the System Prompt - This is crucial for guiding the agent
SYSTEM_PROMPT = """
You are an AI assistant specialized in filling document templates for a bank.
Your goal is to populate a template Word document (.docx) with data extracted from various source documents (like PDF, Excel, other Word files).

**Your Workflow:**

1.  **Identify Needs:** Ask the user for:
    * The path to the template Word document (.docx).
    * The paths to ALL source documents (PDF, Excel, Word) containing the necessary data. Provide them as a list.
    * The desired path for the *output* filled Word document (.docx).

2.  **Analyze Template:**
    * Use the `mcp_run_python.run_python_code` tool to read the template `.docx` file.
    * Identify all placeholders within the template. Assume placeholders are in the format `{{placeholder_name}}`.
    * List the identified placeholders back to the user for confirmation or awareness.

3.  **Extract Data:**
    * For each placeholder identified:
        * Determine the *meaning* of the placeholder (e.g., `{{customer_name}}` means you need the customer's full name).
        * Use the `mcp_run_python.run_python_code` tool to search through the *content* of the provided source documents (PDFs, Excels, Word files) to find the corresponding data.
        * You'll need to generate Python code using libraries like `pypdf` (for PDFs), `pandas`/`openpyxl` (for Excel), and `python-docx` (for Word) to read the files.
        * Prioritize finding the most relevant piece of information for each placeholder.
        * Store the extracted data mapped to its placeholder name (e.g., `{'customer_name': 'John Doe', 'account_number': '123456789'}`).

4.  **Handle Missing Data:** If you cannot find data for a specific placeholder after searching all source documents, inform the user about the missing piece(s). Ask if they want to proceed without it or provide the missing data manually.

5.  **Generate Document:**
    * Once all data is gathered (and the user confirms), use the `mcp_run_python.run_python_code` tool again.
    * Generate Python code that:
        * Loads the original template `.docx` file using `python-docx`.
        * Iterates through the paragraphs and tables of the template.
        * Replaces each found placeholder `{{placeholder_name}}` with its corresponding extracted data.
        * Saves the modified document to the user-specified output path.

**Tool Usage Guidance:**

* **Prefer `mcp_run_python.run_python_code`** for all file reading (PDF, Excel, Word template analysis) and for generating the final Word document. The standard filesystem tool might only give raw text, losing structure.
* When generating Python code for the tool, **ensure necessary imports** (like `docx`, `pypdf`, `pandas`) are included *within the code snippet* you provide to the tool.
* Handle potential file errors (e.g., file not found) gracefully within the Python code you generate.
* Be precise when asking for file paths. Relative paths are acceptable if the filesystem server is configured for the current directory.

**Interaction Style:**
* Be clear and concise.
* Confirm understanding and the extracted data before generating the final document.
* Guide the user through the process.
"""

agent = Agent(
    model=model,
    system_prompt=SYSTEM_PROMPT,
    mcp_servers=servers
)

async def main():
    print("--- Document Filling Agent ---")
    print("Initializing MCP servers...")
    # Keep track of conversation history
    conversation_history = []

    async with agent.run_mcp_servers():
        print("Servers running. Ready to assist.")
        print("Please tell me what template you want to fill and where to find the data.")
        print("Type 'exit', 'quit', or 'bye' to end.")
        print("------------------------------------")

        while True:
            try:
                user_input = input("\n[You] ")

                if user_input.lower() in ['exit', 'quit', 'bye', 'goodbye']:
                    print("Goodbye!")
                    break

                # Add user message to history before sending
                # conversation_history.append({"role": "user", "content": user_input}) # Handled by agent.run

                result = await agent.run(user_input, message_history=conversation_history)

                print('\n[Assistant] ', result.data)

                # Update history with the latest turn (user input + assistant response + tool calls/results)
                conversation_history = result.all_messages()

            except ConnectionError as e:
                 print(f"\nConnection Error: {e}. Please ensure MCP servers are running correctly.")
                 print("You might need to run 'npm install -g @pydantic/mcp-run-python @modelcontextprotocol/server-filesystem' or use npx.")
                 break
            except Exception as e:
                print(f"\nAn unexpected error occurred: {e}")
                # Optionally, you might want to clear history or break depending on the error
                # conversation_history = [] # Clear history on error if needed

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting...")