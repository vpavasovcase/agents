from typing import List, Optional, Dict, Any, Union, cast
from pydantic import BaseModel, Field, ValidationError
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerStdio
import logfire
import os
import asyncio
from dotenv import load_dotenv
from pydantic_ai.models.groq import GroqModel
from pydantic_ai.providers.groq import GroqProvider
from pydantic_ai.common_tools.duckduckgo import duckduckgo_search_tool
import json

"""Sponsor‑finding & email‑drafting CLI agent

Runs a loop that asks for event details, searches the web for 20 potential
sponsors, extracts contact data, and drafts Gmail emails asking for
sponsorship. Uses DuckDuckGo search tool for finding potential sponsors,
Firecrawl for extracting contact information from websites, and Gmail MCP server
for email drafting, all powered by a Groq LLaMA‑4 model.

Safe‑typed throughout so static analysers (e.g. Pylance) do *not* warn about
str.get() errors.
"""

# -------------------------------------------------
# Environment & instrumentation
# -------------------------------------------------
load_dotenv()
logfire.configure()
Agent.instrument_all()

# -------------------------------------------------
# Pydantic models
# -------------------------------------------------
class CityLocation(BaseModel):
    city: str
    country: str

class EventInfo(BaseModel):
    event_type: str
    location: CityLocation
    sponsor_types: Optional[str] = None  # e.g. "local bike shops"

class EmailDraft(BaseModel):
    to: List[str]
    subject: str
    body: str

# Helper alias
JsonListOrDict = Union[List[Any], Dict[str, Any]]

# -------------------------------------------------
# Main workflow
# -------------------------------------------------
async def main() -> None:
    # MCP servers -----------------------------------------------------------
    memory_server = MCPServerStdio("npx", ["-y", "@modelcontextprotocol/server-memory"])
    firecrawl_server = MCPServerStdio(
        "npx",
        ["-y", "firecrawl-mcp"],
        env={"FIRECRAWL_API_KEY": os.getenv("FIRECRAWL_API_KEY", "")},
    )
    gmail_server = MCPServerStdio("npx", ["-y", "@gongrzhe/server-gmail-autoauth-mcp"])

    # LLM & agent -----------------------------------------------------------
    llm_model = GroqModel(
        "meta-llama/llama-4-maverick-17b-128e-instruct",
        provider=GroqProvider(api_key=os.getenv("GROQ_API_KEY", "")),
    )
    agent = Agent(model=llm_model, mcp_servers=[memory_server, firecrawl_server, gmail_server], tools=[duckduckgo_search_tool(max_results=3)], )

    print("=== Sponsorship Email CLI Agent ===")
    print("Type 'exit' at any prompt to quit.\n")

    while True:
        # Input ------------------------------------------------------------
        try:
            event_type = input("Event type (e.g., bike race): ").strip()
            if event_type.lower() == "exit":
                break
            city = input("Event city: ").strip()
            if city.lower() == "exit":
                break
            country = input("Event country: ").strip()
            if country.lower() == "exit":
                break
            sponsor_types = input("Target sponsor types (optional): ").strip()
            if sponsor_types.lower() == "exit":
                break
            sponsor_types = sponsor_types or None

            event_info = EventInfo(
                event_type=event_type,
                location=CityLocation(city=city, country=country),
                sponsor_types=sponsor_types,
            )
        except ValidationError as e:
            print("\n❌ Invalid input:", e, "\n")
            continue

        # One MCP session per event ---------------------------------------
        async with agent.run_mcp_servers():

            # LLM crafts search query ----------------------------------
            query_prompt = (
                "You are helping to find potential business sponsors for the event user is organizing. "
                "Return ONLY a concise web‑search query that will list relevant sponsor websites."\
                "\n\nEvent type: {event}\nCity: {city}\nCountry: {country}\nSponsor types: {types}".format(
                    event=event_info.event_type,
                    city=event_info.location.city,
                    country=event_info.location.country,
                    types=event_info.sponsor_types or "N/A",
                )
            )
            resp = await agent.run(query_prompt)
            search_query = resp.output.strip() if isinstance(resp.output, str) and resp.output.strip() else " ".join(
                [event_info.sponsor_types or event_info.event_type, event_info.location.city, event_info.location.country]
            )
            logfire.info(f"Search query: {search_query}")

            # DuckDuckGo search ----------------------------------------
            # Use the duckduckgo_search_tool through the agent
            search_prompt = (
                f"Search the web for potential sponsors for {event_info.event_type} in {event_info.location.city}, {event_info.location.country}. "
                f"Focus on {event_info.sponsor_types or 'local businesses'}. "
                f"Return a list of 20 relevant company websites that might be interested in sponsoring this event. "
                f"Use the duckduckgo_search tool to find these websites."
            )
            search_response = await agent.run(search_prompt)

            # Extract URLs from the search response
            urls = search_response.output
            print("Search raw output:", urls)

            if not urls:
                print("\n⚠️  No URLs found. Try again.\n")
                continue
            logfire.info(f"Collected {len(urls)} URLs")

            # Extract contacts using Firecrawl ------------------------------
            logfire.info("Extracting contact information from websites using Firecrawl")

            # Process URLs in smaller batches to avoid overwhelming the system
            contacts = []
            batch_size = 1  # Process 1 URL at a time

            for i in range(0, min(len(urls), 10), batch_size):
                batch_urls = urls[i:i+batch_size]
                logfire.info(f"Processing batch {i//batch_size + 1} with {len(batch_urls)} URLs")

                try:
                    # Use agent.run directly with a prompt that instructs the agent to use the firecrawl_extract tool
                    extract_prompt = f"""
                    Use the firecrawl_extract tool to extract contact information from the following URL(s): {batch_urls}.

                    Extract the company name, contact email, and contact person (if available).

                    Use this schema for extraction:
                    {{
                        "type": "object",
                        "properties": {{
                            "name": {{"type": "string", "description": "The company name"}},
                            "email": {{"type": "string", "description": "The contact email address"}},
                            "contact_person": {{"type": "string", "description": "The name of a contact person if available"}}
                        }},
                        "required": ["name"]
                    }}

                    Return the extracted information in JSON format.
                    """

                    extract_response = await agent.run(extract_prompt)
                    extract_raw = extract_response.output

                    logfire.info(f"Extraction result for batch {i//batch_size + 1}: {extract_raw}")

                    # Process the extraction results for this batch
                    # The response from agent.run will be different from call_tool
                    # It will likely be a string that we need to parse for JSON content

                    # Try to extract JSON from the response
                    if isinstance(extract_raw, str):
                        # Look for JSON objects in the string
                        try:
                            # Try to parse the entire string as JSON
                            parsed = json.loads(extract_raw)
                            if isinstance(parsed, list):
                                batch_contacts = [c for c in parsed if isinstance(c, dict) and "name" in c]
                                contacts.extend(batch_contacts)
                            elif isinstance(parsed, dict) and "name" in parsed:
                                contacts.append(parsed)
                            elif isinstance(parsed, dict):
                                # Check if there's a nested structure
                                for key, value in parsed.items():
                                    if isinstance(value, dict) and "name" in value:
                                        contacts.append(value)
                        except json.JSONDecodeError:
                            # Try to find JSON objects in the text
                            import re
                            json_pattern = r'\{[^{}]*\}'
                            json_matches = re.findall(json_pattern, extract_raw)

                            for json_str in json_matches:
                                try:
                                    parsed = json.loads(json_str)
                                    if isinstance(parsed, dict) and "name" in parsed:
                                        contacts.append(parsed)
                                except json.JSONDecodeError:
                                    continue

                    # Handle list or dict responses (less likely with direct agent.run)
                    elif isinstance(extract_raw, list):
                        # Cast to Any to avoid type checking issues
                        from typing import Any
                        extract_list = cast(List[Any], extract_raw)
                        batch_contacts = [c for c in extract_list if isinstance(c, dict) and "name" in c]
                        contacts.extend(batch_contacts)
                    elif isinstance(extract_raw, dict) and "name" in cast(Dict[str, Any], extract_raw):
                        contacts.append(cast(Dict[str, Any], extract_raw))
                except Exception as e:
                    logfire.error(f"Error extracting contact information from batch {i//batch_size + 1}: {str(e)}")

                # Add a small delay between batches to avoid rate limiting
                if i + batch_size < min(len(urls), 10):
                    await asyncio.sleep(2)



            # Check if we found any valid contacts
            if not contacts:
                logfire.error("No contact information extracted from any URL.")

            if not contacts:
                print("\n⚠️  No contacts found.\n")
                continue

            # Draft + save Gmail emails ------------------------------
            for c in contacts:
                print(f"Drafting email for {c}")
                email = cast(str, c.get("email", ""))
                if not email:
                    continue
                name = cast(str, c.get("name", "Valued Sponsor"))
                person = cast(str, c.get("contact_person", "Sir/Madam"))

                subject = f"Sponsorship Invitation: {event_info.event_type} in {event_info.location.city}"
                email_prompt = (
                    f"Compose a polite sponsorship request email to {name} addressed to {person}. "
                    f"The event is a {event_info.event_type} in {event_info.location.city}, {event_info.location.country}. "
                    "Mention their business and request their sponsorship support. Respond ONLY as JSON with keys: to, subject, body. "
                    f"The 'to' field must be ['{email}']."
                )
                resp = await agent.run(email_prompt, output_type=EmailDraft)
                draft: EmailDraft
                if isinstance(resp.output, dict):
                    draft = EmailDraft(**resp.output)
                else:
                    draft = EmailDraft(to=[email], subject=subject, body=str(resp.output))

                # Use agent.run directly with a prompt that instructs the agent to use the draft_email tool
                draft_email_prompt = f"""
                Use the draft_email tool to create a draft email with the following details:

                To: {draft.to}
                Subject: {draft.subject}
                Body: {draft.body}

                Just create the draft, no need to send it.
                """

                await agent.run(draft_email_prompt)
                logfire.info(f"Draft saved for {email}")

            print("\n✅ Draft emails created and saved. Ready for next event.\n")

    print("Goodbye! 👋")

# Entry -------------------------------------------------------------
if __name__ == "__main__":
    asyncio.run(main())
