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

Runs a loop that asks for event details, searches the web for a configurable number
of potential sponsors, extracts contact data, and drafts Gmail emails asking for
sponsorship. Uses DuckDuckGo search tool for finding potential sponsors,
Firecrawl for extracting contact information from websites, and Gmail MCP server
for email drafting, all powered by a Groq LLaMA‑4 model.

Safe‑typed throughout so static analysers (e.g. Pylance) do *not* warn about
str.get() errors.
"""

# -------------------------------------------------
# System Prompt
# -------------------------------------------------
def get_system_prompt(event_type: str = "", city: str = "", country: str = "", sponsor_types: str = "") -> str:
    """Generate a customized system prompt based on event details

    This function creates a system prompt that defines the agent's purpose and behavior.
    The prompt consists of two parts:
    1. A base prompt that explains the agent's general purpose and capabilities
    2. An optional customized section that tailors the agent to a specific event

    Args:
        event_type: Type of event (e.g., "bike race", "charity gala")
        city: City where the event takes place
        country: Country where the event takes place
        sponsor_types: Optional specific types of sponsors to target

    Returns:
        A complete system prompt string for the agent
    """

    base_prompt = f"""
You are a specialized Sponsorship Agent designed to help users find and contact potential sponsors for events.

Your primary functions are:
1. Analyze event details (type, location, target sponsor types) to craft effective search queries
2. Search the web for relevant potential sponsors using DuckDuckGo
3. Extract company information from sponsor websites using Firecrawl
4. Draft personalized sponsorship request emails and save them to Gmail

When searching for sponsors:
- Focus on businesses relevant to the event type and location
- Prioritize companies with accessible contact information
- Consider businesses that have sponsored similar events in the past
- Look for local businesses that would benefit from association with the event

When extracting company information:
- Find the official company name
- Locate contact email addresses (preferably for sponsorship or marketing departments)
- Keep in mind the sites are in language of country {country}

When drafting sponsorship emails:
- Personalize each email to the specific company
- Clearly explain the event and its relevance to the company
- Highlight mutual benefits of sponsorship
- Be professional, concise, and compelling
- Include specific details about the event that make it attractive for sponsorship

You will operate through a command-line interface, guiding users through the process of finding and contacting sponsors efficiently.
"""

    # Add customization if event details are provided
    if event_type and city and country:
        custom_section = f"""
Current Event Details:
- Event Type: {event_type}
- Location: {city}, {country}
- Target Sponsor Types: {sponsor_types or "Any relevant local businesses"}

For this specific event, focus on finding sponsors that would be particularly interested in {event_type} events.
Consider the local business environment in {city}, {country} and prioritize companies that have a connection to the event theme or location.
"""
        return base_prompt + custom_section

    return base_prompt

# -------------------------------------------------
# Environment & instrumentation
# -------------------------------------------------
load_dotenv()
logfire.configure()
Agent.instrument_all()

# -------------------------------------------------
# Constants
# -------------------------------------------------
MAX_SPONSORS = 3  # Maximum number of potential sponsors to find

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

    # We'll create a customized agent for each event session

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

            # Create a customized system prompt for this event
            custom_prompt = get_system_prompt(
                event_type=event_info.event_type,
                city=event_info.location.city,
                country=event_info.location.country,
                sponsor_types=event_info.sponsor_types or ""
            )

            # Create a new agent with the customized system prompt
            # We'll use this agent for this specific event session
            event_agent = Agent(
                model=llm_model,
                system_prompt=custom_prompt,
                mcp_servers=[memory_server, firecrawl_server, gmail_server],
                tools=[duckduckgo_search_tool(max_results=MAX_SPONSORS)],
                retries=3,
            )

            print(f"\n✅ Agent customized for: {event_info.event_type} in {event_info.location.city}, {event_info.location.country}")
            print(f"\n✅ System prompt: {custom_prompt}")

        except ValidationError as e:
            print("\n❌ Invalid input:", e, "\n")
            continue

        # One MCP session per event ---------------------------------------
        async with event_agent.run_mcp_servers():

            # LLM crafts search query ----------------------------------
            query_prompt = (
                "Return ONLY a concise web‑search query that will list relevant sponsor websites."\
                "\n\nEvent type: {event}\nCity: {city}\nCountry: {country}\nSponsor types: {types}".format(
                    event=event_info.event_type,
                    city=event_info.location.city,
                    country=event_info.location.country,
                    types=event_info.sponsor_types or "N/A",
                )
            )
            resp = await event_agent.run(query_prompt)
            search_query = resp.output.strip() if isinstance(resp.output, str) and resp.output.strip() else " ".join(
                [event_info.sponsor_types or event_info.event_type, event_info.location.city, event_info.location.country]
            )
            logfire.info(f"Search query: {search_query}")

            # DuckDuckGo search ----------------------------------------
            # Use the duckduckgo_search_tool through the agent
            search_prompt = (
                f"INSTRUCTIONS: Make EXACTLY ONE search using the duckduckgo_search tool. No more, no less.\n\n"
                f"Search query to use: '{search_query}'\n\n"
                f"Context: Looking for potential sponsors for {event_info.event_type} in {event_info.location.city}, {event_info.location.country}. "
                f"Focus on {event_info.sponsor_types or 'local businesses'}.\n\n"
                f"Return format: A list of up to {MAX_SPONSORS} URLs to company websites. Format your response as a numbered list with ONLY the URLs, one per line, like this:\n"
                f"1. https://example1.com\n"
                f"2. https://example2.com\n"
                f"3. https://example3.com\n\n"
                f"CRITICAL: Make only ONE call to the duckduckgo_search tool. Do not make multiple search calls."
            )
            search_response = await event_agent.run(search_prompt)
            logfire.info("Received search response from agent")

            # Extract URLs from the search response
            search_output = search_response.output
            print("Search output:", search_output)
            logfire.info(f"Search response type: {type(search_output)}")
            logfire.debug(f"Search response: {search_response.output}")


            # Parse URLs from the search response string
            urls = []

            if isinstance(search_output, str):
                # Look for URLs in the text using a more robust pattern matching approach
                import re
                # This pattern matches URLs more accurately, including those in numbered lists
                url_pattern = r'(?:https?://(?:www\.)?|www\.)[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+(?:/[^\s\)\]\"\']*)*'
                urls = re.findall(url_pattern, search_output)

                # Clean up URLs to ensure they have proper http/https prefix
                cleaned_urls = []
                for url in urls:
                    if not url.startswith(('http://', 'https://')):
                        url = 'https://' + url
                    cleaned_urls.append(url)
                urls = cleaned_urls
            elif isinstance(search_output, list):
                # If by chance it's already a list, use it directly
                urls = search_output

            # Remove duplicate URLs while preserving order
            unique_urls = []
            seen = set()
            for url in urls:
                if url not in seen:
                    seen.add(url)
                    unique_urls.append(url)
            urls = unique_urls


            logfire.debug(f"URLs: {urls}")

            if not urls:
                print("\n⚠️  No URLs found. Try again.\n")
                continue

            # Print the extracted URLs for debugging
            print("\nExtracted URLs:")
            for i, url in enumerate(urls[:MAX_SPONSORS], 1):
                print(f"{i}. {url}")
            print()

            logfire.info(f"Collected {len(urls)} unique URLs")

            # Extract contacts using Firecrawl ------------------------------
            logfire.info("Extracting contact information from websites using Firecrawl")

            # Process URLs one at a time
            contacts = []

            for url in urls[:MAX_SPONSORS]:

                try:
                    # Use event_agent.run directly with a prompt that instructs the agent to use the firecrawl_extract tool
                    extract_prompt = f"""
                    Use the firecrawl crawl tool to analyze this website: {url}, and find the company name, contact email, and contact person (if available).
                    Return the extracted information in JSON format.
                    """

                    extract_response = await event_agent.run(extract_prompt)
                    extract_raw = extract_response.output

                    logfire.info(f"Extraction result for url {url}: {extract_raw}")

                    # Process the extraction results for this batch
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
                    logfire.error(f"Error extracting contact information from url {url}: {str(e)}")
                
                # Add a delay of 5 seconds after each loop iteration
                await asyncio.sleep(5)

            # Check if we found any valid contacts

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
                resp = await event_agent.run(email_prompt, output_type=EmailDraft)
                draft: EmailDraft
                if isinstance(resp.output, dict):
                    draft = EmailDraft(**resp.output)
                else:
                    draft = EmailDraft(to=[email], subject=subject, body=str(resp.output))

                # Use event_agent.run directly with a prompt that instructs the agent to use the draft_email tool
                draft_email_prompt = f"""
                Use the draft_email tool to create a draft email with the following details:

                The recipient email is {draft.to[0]}, the subject is '{draft.subject}', and the body is:

                {draft.body}

                Just create the draft, no need to send it.
                """

                await event_agent.run(draft_email_prompt)
                logfire.info(f"Draft saved for {email}")

            print("\n✅ Draft emails created and saved. Ready for next event.\n")

    print("Goodbye! 👋")

# Entry -------------------------------------------------------------
if __name__ == "__main__":
    asyncio.run(main())
