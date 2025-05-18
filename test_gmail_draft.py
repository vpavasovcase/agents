#!/usr/bin/env python3
"""
Test script for Gmail MCP server draft email functionality.
This script creates a hardcoded draft email using the Gmail MCP server.
"""

import asyncio
import os
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerStdio
from pydantic_ai.models.groq import GroqModel
from pydantic_ai.providers.groq import GroqProvider
from dotenv import load_dotenv
import logfire

# Load environment variables
load_dotenv()
logfire.configure()

async def test_gmail_draft():
    """Test the Gmail MCP server draft email functionality with a hardcoded example."""
    
    print("=== Gmail Draft Email Test ===")
    
    # Initialize MCP server for Gmail
    gmail_server = MCPServerStdio("npx", ["-y", "@gongrzhe/server-gmail-autoauth-mcp"])
    
    # Initialize LLM model
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
    
    # Run the MCP servers
    async with test_agent.run_mcp_servers():
        print("MCP servers started")
        
        # Create a hardcoded draft email prompt
        draft_email_prompt = f"""
        Use the draft_email tool to create a draft email with the following details:

        The recipient email is {test_recipient}, the subject is 'Test Draft Email', and the body is:

        This is a test email draft created by the Gmail MCP server test script.
        
        Please ignore this draft as it is only for testing purposes.

        Just create the draft, no need to send it.
        """
        
        print("Sending draft email request...")
        
        # Run the agent with the draft email prompt
        try:
            response = await test_agent.run(draft_email_prompt)
            print(f"Response: {response.output}")
            print("\n✅ Test completed. Check your Gmail drafts folder to verify the draft was created.")
        except Exception as e:
            print(f"❌ Error creating draft email: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_gmail_draft())
