#!/usr/bin/env python3
"""
Test script for Gmail MCP server draft email functionality.
This script mimics the approach used in main_vojo.py.
"""

import asyncio
import os
from pydantic import BaseModel
from typing import List, Optional
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerStdio
from pydantic_ai.models.groq import GroqModel
from pydantic_ai.providers.groq import GroqProvider
from dotenv import load_dotenv
import logfire

# Load environment variables
load_dotenv()
logfire.configure()

# Define the EmailDraft model as in main_vojo.py
class EmailDraft(BaseModel):
    to: List[str]
    subject: str
    body: str

async def test_gmail_draft_vojo():
    """Test the Gmail MCP server draft email functionality using the approach in main_vojo.py."""
    
    print("=== Gmail Draft Email Vojo Test ===")
    
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
        
        # Create a draft email
        email = "test@example.com"
        name = "Test Company"
        person = "Test Person"
        subject = "Test Sponsorship Invitation"
        
        # First, get the email content using the agent
        email_prompt = (
            f"Compose a polite sponsorship request email to {name} addressed to {person}. "
            f"The event is a test event in Test City, Test Country. "
            "Mention their business and request their sponsorship support. Respond ONLY as JSON with keys: to, subject, body. "
            f"The 'to' field must be ['{email}']."
        )
        
        print("Getting email content...")
        resp = await test_agent.run(email_prompt, output_type=EmailDraft)
        
        # Create the draft
        draft: EmailDraft
        if isinstance(resp.output, dict):
            draft = EmailDraft(**resp.output)
        else:
            draft = EmailDraft(to=[email], subject=subject, body=str(resp.output))
        
        print(f"Draft created: {draft}")
        
        # Use the draft_email tool to create the draft in Gmail
        draft_email_prompt = f"""
        Use the draft_email tool to create a draft email with the following details:

        The recipient email is {draft.to[0]}, the subject is '{draft.subject}', and the body is:

        {draft.body}

        Just create the draft, no need to send it.
        """
        
        print("Creating draft in Gmail...")
        draft_response = await test_agent.run(draft_email_prompt)
        
        print(f"Draft response: {draft_response.output}")
        print("\n✅ Test completed. Check your Gmail drafts folder to verify the draft was created.")

if __name__ == "__main__":
    asyncio.run(test_gmail_draft_vojo())
