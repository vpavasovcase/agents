from typing import List, Optional
from pydantic import BaseModel, Field, ValidationError
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerStdio
import logfire
import os
import asyncio
from dotenv import load_dotenv
from pydantic_ai.models.groq import GroqModel
from pydantic_ai.providers.groq import GroqProvider

load_dotenv()
logfire.configure()
Agent.instrument_all()

# ------------------------------------------
# Pydantic data models for structured input
# ------------------------------------------
class CityLocation(BaseModel):
    """
    Validates and stores city and country for the event location.
    """
    city: str
    country: str

class EventInfo(BaseModel):
    """
    Validates user input for the event information.
    """
    event_type: str
    location: CityLocation
    sponsor_types: Optional[str] = None  # e.g. "local sports shops"

class EmailDraft(BaseModel):
    """
    Represents the structured email draft for the Gmail MCP.
    """
    to: List[str] = Field(..., description="Recipient email address(es)")
    subject: str = Field(..., description="Email subject line")
    body: str = Field(..., description="Email body text")

async def main():
    # ------------------------------------------
    # Setup Logfire for logging operations
    # ------------------------------------------

    # ------------------------------------------
    # Configure MCP servers (Memory, Firecrawl, Gmail)
    # ------------------------------------------
    # Memory server (knowledge graph memory)

    memory_server =  MCPServerStdio("npx", ["-y", "@modelcontextprotocol/server-memory"])
    # Firecrawl server (web search/scraping)
    firecrawl_server = MCPServerStdio(
        "npx",
        ["-y", "firecrawl-mcp"],
        env={"FIRECRAWL_API_KEY": os.getenv("FIRECRAWL_API_KEY", "")},
    )
    # Gmail server (Gmail integration)
    gmail_server = MCPServerStdio("npx", ["@gongrzhe/server-gmail-autoauth-mcp"])

    

    # ------------------------------------------
    # Create the PydanticAI agent
    # ------------------------------------------
    # Use Groq LLaMA 4 model, with MCP servers registered, and enable instrumentation
    llm_model = GroqModel(
    "meta-llama/llama-4-maverick-17b-128e-instruct",
    provider=GroqProvider(api_key=os.getenv("GROQ_API_KEY", "")),
)

    agent = Agent(
        model=llm_model,
        mcp_servers=[memory_server, firecrawl_server, gmail_server],
    )

    print("=== Sponsorship Email CLI Agent ===")
    print("Enter event details to generate sponsorship emails (or type 'exit' to quit).")
    while True:
        try:
            # Prompt user for event details
            event_type = input("Event type (e.g., bike race, food festival): ").strip()
            if event_type.lower() == 'exit':
                break
            city = input("Event city: ").strip()
            if city.lower() == 'exit':
                break
            country = input("Event country: ").strip()
            if country.lower() == 'exit':
                break
            sponsor_types = input("Target sponsor types (optional): ").strip()
            if sponsor_types.lower() == 'exit':
                break
            sponsor_types = sponsor_types or None

            # Validate structured data using Pydantic
            event_info = EventInfo(
                event_type=event_type,
                location=CityLocation(city=city, country=country),
                sponsor_types=sponsor_types
            )
        except ValidationError as e:
            print("Error: Invalid input.", e)
            continue

        # Log the received input
        logfire.info(f"Event: {event_info.event_type}, Location: {event_info.location.city}, {event_info.location.country}, Sponsors: {event_info.sponsor_types}")

        # ------------------------------------------
        # (Optional) Use Memory server to store event context
        # ------------------------------------------
        # E.g., create an entity for the event in memory
        async with agent.run_mcp_servers():
            await agent.run(
                f'create_entities entities=[{{"name": "{event_info.event_type}", "entityType": "event", '
                f'"observations": ["Location: {event_info.location.city}, {event_info.location.country}"]}}]'
            )

        # ------------------------------------------
        # Use Firecrawl to search for relevant businesses
        # ------------------------------------------
        # Build the search query
        query_parts = []
        if event_info.sponsor_types:
            query_parts.append(event_info.sponsor_types)
        else:
            query_parts.append(event_info.event_type)
        query_parts.append(event_info.location.city)
        query_parts.append(event_info.location.country)
        search_query = " ".join(query_parts)
        logfire.info(f"Performing web search for: \"{search_query}\"")

        # Firecrawl 'search' tool invocation
        search_args = {
            "name": "firecrawl_search",
            "arguments": {
                "query": search_query,
                "limit": 20,
                "lang": "en",
                "country": event_info.location.country[:2].lower(),
                "scrapeOptions": {
                    "formats": ["markdown"],
                    "onlyMainContent": True
                }
            }
        }
        # Run the Firecrawl search via MCP
        async with agent.run_mcp_servers():
            search_result = await agent.run(str(search_args))
        logfire.info("Web search completed.")

        # Extract URLs from the search results output
        urls = []
        if search_result.output:
            for line in search_result.output.strip().splitlines():
                line = line.strip()
                if line.startswith("http"):
                    urls.append(line)
        urls = urls[:20]  # ensure we have at most 20 URLs
        logfire.info(f"Found {len(urls)} website URLs to scrape.")

        # ------------------------------------------
        # Use Firecrawl to extract contact info from websites
        # ------------------------------------------
        extract_prompt = (
            "Extract the company name, contact email, and contact person (if available) "
            "from the given web page."
        )
        extract_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "email": {"type": "string"},
                "contact_person": {"type": "string"}
            },
            "required": ["name", "email"]
        }
        extract_args = {
            "name": "firecrawl_extract",
            "arguments": {
                "urls": urls,
                "prompt": extract_prompt,
                "systemPrompt": "You are an assistant that extracts structured info from web pages.",
                "schema": extract_schema,
                "allowExternalLinks": False,
                "enableWebSearch": False,
                "includeSubdomains": False
            }
        }
        async with agent.run_mcp_servers():
            extract_result = await agent.run(str(extract_args))
        logfire.info("Information extraction from websites completed.")

        # Parse the extracted contacts (expecting JSON output)
        contacts = []
        if extract_result.output:
            import json
            try:
                contacts = json.loads(extract_result.output)
            except json.JSONDecodeError:
                logfire.error("Failed to parse extraction output; skipping email generation.")
                contacts = []

        # ------------------------------------------
        # Generate and save emails for each contact
        # ------------------------------------------
        for contact in contacts:
            name = contact.get("name", "Valued Sponsor")
            email = contact.get("email")
            person = contact.get("contact_person", "Sir/Madam")
            if not email:
                continue  # skip if no email found
            logfire.info(f"Generating email for {name} (Contact: {person}, Email: {email})")

            # Define email content prompt for LLaMA 4
            subject = f"Sponsorship Invitation: {event_info.event_type} in {event_info.location.city}"
            email_prompt = (
                f"Compose a polite sponsorship request email to {name} addressed to {person}. "
                f"The event is a {event_info.event_type} in {event_info.location.city}, {event_info.location.country}. "
                "Mention their business and request their sponsorship support. "
                "Format the output as JSON with keys: to (list of emails), subject, body. "
                f"The 'to' field should be [\"{email}\"]."
            )
            async with agent.run_mcp_servers():
                email_result = await agent.run(email_prompt, output_type=EmailDraft)
            if email_result.output:
                draft = EmailDraft(**email_result.output) if isinstance(email_result.output, dict) else email_result.output
            else:
                # Fallback if model output isn't structured correctly
                draft = EmailDraft(to=[email], subject=subject, body=str(email_result.output))
            logfire.info(f"Draft email subject: {draft.subject}")

            # Prepare Gmail MCP 'draft_email' tool call
            gmail_args = {
                "name": "draft_email",
                "arguments": {
                    "to": draft.to,
                    "subject": draft.subject,
                    "body": draft.body
                }
            }
            async with agent.run_mcp_servers():
                await agent.run(str(gmail_args))
            logfire.info(f"Saved email draft for {name} ({email}).")

        print("Draft emails created and saved to Gmail. Ready for next event.\n")
    print("Agent loop exited. Goodbye!")

if __name__ == "__main__":
    asyncio.run(main())
