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
# Helper
# -------------------------------------------------
async def call_tool(agent: Agent, spec: Any) -> Any:
    """Call an MCP tool and return its raw output."""
    from typing import cast
    return (await agent.run(cast(Any, spec))).output

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
    agent = Agent(model=llm_model, mcp_servers=[memory_server, firecrawl_server, gmail_server], tools=[duckduckgo_search_tool(max_results=20)], )

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
            search_raw = search_response.output

            urls: List[str] = []
            # Handle DuckDuckGo search results
            logfire.info(f"Search response type: {type(search_raw)}")

            # Try to extract URLs from the response in various formats
            if isinstance(search_raw, dict):
                # Check for standard DuckDuckGo tool response format
                if "results" in search_raw:
                    for item in search_raw.get("results", []):
                        if isinstance(item, dict):
                            url = cast(str, item.get("url") or item.get("href") or item.get("link") or "")
                            if url:
                                urls.append(url)

                # Check for all_messages_events format
                if "all_messages_events" in search_raw:
                    for event in search_raw.get("all_messages_events", []):
                        if isinstance(event, dict) and event.get("role") == "tool" and event.get("name") == "duckduckgo_search":
                            content = event.get("content", [])
                            if isinstance(content, list):
                                for item in content:
                                    if isinstance(item, dict):
                                        url = cast(str, item.get("href") or item.get("url") or item.get("link") or "")
                                        if url and url.startswith("http"):
                                            urls.append(url)

            elif isinstance(search_raw, list):
                # Handle list of results
                for obj in search_raw:
                    if isinstance(obj, dict):
                        url = cast(str, obj.get("url") or obj.get("href") or obj.get("link") or "")
                        if url:
                            urls.append(url)
                    elif isinstance(obj, str) and obj.startswith("http"):
                        urls.append(obj)

            elif isinstance(search_raw, str):
                # Try to parse as JSON
                try:
                    json_data = json.loads(search_raw)
                    if isinstance(json_data, dict) or isinstance(json_data, list):
                        # Recursively call this section with the parsed JSON
                        if isinstance(json_data, dict):
                            # Check for standard DuckDuckGo tool response format
                            if "results" in json_data:
                                for item in json_data.get("results", []):
                                    if isinstance(item, dict):
                                        url = cast(str, item.get("url") or item.get("href") or item.get("link") or "")
                                        if url:
                                            urls.append(url)

                            # Check for all_messages_events format
                            if "all_messages_events" in json_data:
                                for event in json_data.get("all_messages_events", []):
                                    if isinstance(event, dict) and event.get("role") == "tool" and event.get("name") == "duckduckgo_search":
                                        content = event.get("content", [])
                                        if isinstance(content, list):
                                            for item in content:
                                                if isinstance(item, dict):
                                                    url = cast(str, item.get("href") or item.get("url") or item.get("link") or "")
                                                    if url and url.startswith("http"):
                                                        urls.append(url)
                except json.JSONDecodeError:
                    # Fallback for plain text
                    for line in search_raw.splitlines():
                        if line.strip().startswith("http"):
                            urls.append(line.strip())

            # Final fallback for any other format
            if not urls:
                text_repr = str(search_raw)
                for line in text_repr.splitlines():
                    if "http" in line:
                        # Extract URLs from the line
                        import re
                        url_pattern = r'https?://[^\s"\'<>)]+'
                        found_urls = re.findall(url_pattern, line)
                        urls.extend(found_urls)

            # Log the extracted URLs
            logfire.info(f"Extracted {len(urls)} URLs from search results")

            urls = urls[:20]
            if not urls:
                print("\n⚠️  No URLs found. Try again.\n")
                continue
            logfire.info(f"Collected {len(urls)} URLs")

            # Extract contacts using Firecrawl ------------------------------
            logfire.info("Extracting contact information from websites using Firecrawl")

            # Use Firecrawl to extract contact information from all URLs at once
            extract_raw = await call_tool(
                agent,
                {
                    "name": "firecrawl_extract",
                    "arguments": {
                        "urls": urls[:10],  # Process first 10 URLs
                        "prompt": "Extract the company name, contact email, and contact person (if available).",
                        "schema": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "email": {"type": "string"},
                                "contact_person": {"type": "string"},
                            },
                            "required": ["name", "email"],
                        },
                    },
                },
            )

            # Process the extraction results
            contacts: List[Dict[str, Any]] = []
            if isinstance(extract_raw, list):
                contacts = [c for c in extract_raw if isinstance(c, dict)]
            elif isinstance(extract_raw, str):
                try:
                    parsed = json.loads(extract_raw)
                    if isinstance(parsed, list):
                        contacts = [c for c in parsed if isinstance(c, dict)]
                    elif isinstance(parsed, dict):
                        contacts = [parsed]
                except json.JSONDecodeError:
                    logfire.error("Could not parse Firecrawl extraction output.")

            # contacts list is already populated from the previous step
            if not contacts:
                logfire.error("No contact information extracted from any URL.")

            if not contacts:
                print("\n⚠️  No contacts found.\n")
                continue

            # Draft + save Gmail emails ------------------------------
            for c in contacts:
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

                await call_tool(
                    agent,
                    {
                        "name": "draft_email",
                        "arguments": {"to": draft.to, "subject": draft.subject, "body": draft.body},
                    },
                )
                logfire.info(f"Draft saved for {email}")

            print("\n✅ Draft emails created and saved. Ready for next event.\n")

    print("Goodbye! 👋")

# Entry -------------------------------------------------------------
if __name__ == "__main__":
    asyncio.run(main())
