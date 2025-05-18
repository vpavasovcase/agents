#!/usr/bin/env python3
"""
Direct test script for Gmail MCP server draft email functionality.
This script directly calls the draft_email method of the Gmail MCP server.
"""

import asyncio
import os
import json
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerStdio
from pydantic_ai.models.groq import GroqModel
from pydantic_ai.providers.groq import GroqProvider
from dotenv import load_dotenv
import logfire

# Load environment variables
load_dotenv()
logfire.configure()

async def test_gmail_draft_direct():
    """Test the Gmail MCP server draft_email method directly."""

    print("=== Gmail Draft Email Direct Test ===")

    # Initialize MCP server for Gmail
    gmail_server = MCPServerStdio("npx", ["-y", "@gongrzhe/server-gmail-autoauth-mcp"])

    # Initialize LLM model (needed for Agent)
    llm_model = GroqModel(
        "meta-llama/llama-4-maverick-17b-128e-instruct",
        provider=GroqProvider(api_key=os.getenv("GROQ_API_KEY", "")),
    )

    # Create a simple agent with the Gmail MCP server
    test_agent = Agent(
        model=llm_model,
        system_prompt="You are a test agent for creating Gmail draft emails.",
        mcp_servers=[gmail_server],
        retries=3,
    )

    # Test recipient email - replace with a valid test email
    test_recipient = "test@example.com"

    # Use the run_mcp_servers context manager
    async with test_agent.run_mcp_servers():
        print("Gmail MCP server started")

        try:
            # Create draft email parameters
            draft_params = {
                "to": [test_recipient],
                "subject": "Test Draft Email Direct",
                "body": "This is a test email draft created directly by calling the draft_email method.\n\nPlease ignore this draft as it is only for testing purposes."
            }

            print(f"Calling draft_email method with parameters: {draft_params}")

            # Create a direct instruction for the agent to use the draft_email tool
            instruction = """
            Use the draft_email tool with exactly these parameters:
            {
                "to": ["test@example.com"],
                "subject": "Test Draft Email Direct",
                "body": "This is a test email draft created directly. Please ignore this draft as it is only for testing purposes."
            }

            Do not modify the parameters. Use them exactly as provided.
            """

            # Run the agent with the direct instruction
            result = await test_agent.run(instruction)

            # Print the result output directly (no need for JSON serialization)
            print(f"Result output: {result.output}")
            print("\n✅ Test completed. Check your Gmail drafts folder to verify the draft was created.")
        except Exception as e:
            print(f"❌ Error creating draft email: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_gmail_draft_direct())
