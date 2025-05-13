import asyncio
import os
from typing import List, Optional, Literal

import logfire
from dotenv import load_dotenv
from pydantic import BaseModel, HttpUrl, EmailStr

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel # Or any other model you prefer
from pydantic_ai.providers.openai import OpenAIProvider # Or your chosen provider
from pydantic_ai.mcp import MCPServer, MCPServerStdio # Assuming local MCP servers

# --- Configuration ---
load_dotenv(override=True)
logfire.configure() # Basic Logfire configuration

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable not set.")

# --- Pydantic Models for Structured Data ---

class SponsorshipInquiryContext(BaseModel):
    event_description: str
    event_location: str
    target_sponsor_type: str # e.g., "bicycle shops", "local businesses"

class SearchedUrl(BaseModel):
    url: HttpUrl
    source: str # e.g., "DuckDuckGo"

class CompanyInfo(BaseModel):
    company_name: str
    website_url: HttpUrl
    contact_email: Optional[EmailStr] = None
    contact_person: Optional[str] = None
    reason_for_suitability: Optional[str] = None # Why the WebCrawl agent thinks it's suitable
    raw_scraped_data: Optional[str] = None # Or a more structured model for scraped data

class UrlMemoryEntry(BaseModel):
    url: HttpUrl
    status: Literal["pending_crawl", "suitable_contacted", "unsuitable", "crawl_failed"]
    company_info: Optional[CompanyInfo] = None # Store if suitable

class EmailDraft(BaseModel):
    recipient_email: EmailStr
    recipient_name: Optional[str] = None
    subject: str
    body: str
    company_url: HttpUrl

# --- MCP Server Definitions ---
# Adjust these paths and commands based on your actual MCP server setup.
# Ensure these servers are running or can be started by PydanticAI.

# 1. Memory Server ([https://github.com/modelcontextprotocol/servers/tree/main/src/memory](https://github.com/modelcontextprotocol/servers/tree/main/src/memory))
#    You'll need to have this server running. The PydanticAI library
#    will then connect to it. If it's a local server started with npx:
MEMORY_MCP_SERVER_COMMAND = ['npx', '-y', '@modelcontextprotocol/server-memory', 'stdio'] # Example, adjust as needed

# 2. Web Crawl Server (Firecrawl - [https://github.com/mendableai/firecrawl-mcp-server](https://github.com/mendableai/firecrawl-mcp-server))
FIRECRAWL_MCP_SERVER_COMMAND = ['npx', '-y', '@mendableai/firecrawl-mcp-server', 'stdio'] # Example

# 3. Gmail MCP Server ([https://github.com/GongRzhe/Gmail-MCP-Server](https://github.com/GongRzhe/Gmail-MCP-Server))
GMAIL_MCP_SERVER_COMMAND = ['npx', '-y', '@gongrzhe/gmail-mcp-server', 'stdio'] # Example, check actual package name if different

# 4. DuckDuckGo (if no direct MCP server, you might need a custom tool or direct library use)
#    For simplicity, we'll assume a tool can be created or PydanticAI's built-in capabilities
#    can be leveraged if an MCP server for DuckDuckGo is available or you make one.
#    Alternatively, the WebSearch agent can directly use a library like `duckduckgo_search`.
#    PydanticAI documentation on common tools: [https://ai.pydantic.dev/common-tools/](https://ai.pydantic.dev/common-tools/)
#    If using a standard PydanticAI tool that doesn't require a separate MCP server process:
DUCKDUCKGO_TOOL_ID = "duckduckgo_search" # This is a placeholder, actual tool ID might differ

mcp_servers_config = [
    # MCPServerStdio(cmd=MEMORY_MCP_SERVER_COMMAND[0], args=MEMORY_MCP_SERVER_COMMAND[1:]),
    # MCPServerStdio(cmd=FIRECRAWL_MCP_SERVER_COMMAND[0], args=FIRECRAWL_MCP_SERVER_COMMAND[1:]),
    # MCPServerStdio(cmd=GMAIL_MCP_SERVER_COMMAND[0], args=GMAIL_MCP_SERVER_COMMAND[1:]),
    # Note: You need to ensure these servers are correctly configured and PydanticAI can connect.
    # The example in your prompt used absolute paths for some servers, adapt as needed.
    # For servers not managed by PydanticAI directly (e.g., hosted elsewhere),
    # you'd use MCPServer(url="http://localhost:PORT")
]

# --- Agent Definitions ---

# Base LLM Model
llm_model = OpenAIModel(
    "gpt-4o", # Or your preferred model
    provider=OpenAIProvider(api_key=OPENAI_API_KEY)
)

# 0. Memory Agent (Interface to the Memory MCP Server)
# This isn't an "agent" in the LLM sense, but a client to the memory service.
# We'll interact with it via PydanticAI's MCP capabilities.
# Functions would be like:
# async def get_url_status(url: HttpUrl) -> Optional[UrlMemoryEntry]: ...
# async def store_url_status(entry: UrlMemoryEntry): ...
# These would be implemented by making calls to the memory MCP server.

# 1. WebSearch Agent
async def web_search_agent_logic(
    inquiry: SponsorshipInquiryContext,
    mcp_servers: List[MCPServer] # PydanticAI will pass configured servers
) -> List[SearchedUrl]:
    """
    Pretraži web za firme koje bi mogle biti zainteresirane za event.
    """
    logfire.info(f"WebSearchAgent: Starting search for '{inquiry.target_sponsor_type}' related to '{inquiry.event_description}' in '{inquiry.event_location}'.")

    # This agent would use the DuckDuckGo tool (or another search tool)
    # via the mcp_servers or a direct integration if PydanticAI supports it.
    search_query = f"{inquiry.target_sponsor_type} in {inquiry.event_location} sponsorship {inquiry.event_description}"

    # --- Simulate calling DuckDuckGo MCP Tool ---
    # This part is conceptual. How you call an MCP tool depends on PydanticAI's
    # mechanisms. You might define a Pydantic model for the tool input and output.
    # For example:
    # duckduckgo_mcp = next((s for s in mcp_servers if "duckduckgo" in s.id_or_url_or_cmd), None) # Find the server
    # if duckduckgo_mcp:
    #     response = await duckduckgo_mcp.call_method("search", query=search_query, max_results=20)
    #     search_results = [SearchedUrl(url=res['link'], source="DuckDuckGo") for res in response.get("results", [])]
    # else:
    #     print("DuckDuckGo MCP server not configured. Using placeholder results.")
    #     search_results = []

    # Placeholder if not using MCP for DuckDuckGo directly, or using a library
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = ddgs.text(search_query, max_results=20)
            search_results = [SearchedUrl(url=r['href'], source="DuckDuckGo") for r in results if r.get('href')]
            logfire.info(f"WebSearchAgent: Found {len(search_results)} results.")
    except ImportError:
        logfire.error("WebSearchAgent: duckduckgo_search library not installed. Please install it: pip install duckduckgo-search")
        search_results = []
    except Exception as e:
        logfire.error(f"WebSearchAgent: Error during DuckDuckGo search: {e}")
        search_results = []


    return search_results[:20] # Ensure only 20 results

# 2. WebCrawl Agent
async def web_crawl_agent_logic(
    url_to_crawl: HttpUrl,
    sponsorship_context: SponsorshipInquiryContext,
    mcp_servers: List[MCPServer]
) -> Optional[CompanyInfo]:
    """
    Pročita sajt, procijeni prikladnost i izvuče podatke o firmi.
    """
    logfire.info(f"WebCrawlAgent: Crawling {url_to_crawl}")

    # --- Call Firecrawl MCP Server ---
    # firecrawl_mcp = next((s for s in mcp_servers if "firecrawl" in s.id_or_url_or_cmd), None) # Conceptual
    # if not firecrawl_mcp:
    #     logfire.error("Firecrawl MCP server not configured.")
    #     return None
    #
    # try:
    #     # The actual method and parameters will depend on the Firecrawl MCP server's API
    #     crawl_response = await firecrawl_mcp.call_method("crawl", url=str(url_to_crawl))
    #     scraped_data_text = crawl_response.get("content", "") # or "markdown" or "data"
    # except Exception as e:
    #     logfire.error(f"WebCrawlAgent: Error crawling {url_to_crawl} with Firecrawl: {e}")
    #     return None

    # Placeholder for direct Firecrawl usage if MCP is not set up yet
    # You would use the firecrawl-py library here
    scraped_data_text = f"Simulated scraped data for {url_to_crawl}. About us: We love {sponsorship_context.target_sponsor_type}. Contact: contact@{url_to_crawl.host}."
    logfire.info(f"WebCrawlAgent: Successfully scraped {url_to_crawl}. Data length: {len(scraped_data_text)}")


    # --- Use LLM to evaluate suitability and extract info ---
    evaluation_prompt = f"""
    Based on the following scraped text from the website {url_to_crawl},
    and the sponsorship context:
    Event Description: {sponsorship_context.event_description}
    Event Location: {sponsorship_context.event_location}
    Target Sponsor Type: {sponsorship_context.target_sponsor_type}

    1. Is this company potentially a good sponsor? (Provide a brief reason)
    2. What is the company name?
    3. Is there a contact email?
    4. Is there a contact person's name?

    Scraped Text:
    ---
    {scraped_data_text[:3000]}
    ---
    Respond with a JSON object with keys: "is_suitable" (boolean), "reason_for_suitability" (string), "company_name" (string), "contact_email" (string, or null), "contact_person" (string, or null).
    """
    try:
        extraction_agent = Agent(
            model=llm_model,
            system_prompt="You are an assistant that extracts company information and assesses sponsorship suitability from website text.",
            # mcp_servers=mcp_servers # If needed for sub-tasks, though likely not for this simple extraction
        )
        # This is a simplified way to get structured output. PydanticAI offers more robust ways.
        # You might define a Pydantic model for the extraction output and pass it to `agent.run`.
        class ExtractedInfo(BaseModel):
            is_suitable: bool
            reason_for_suitability: Optional[str] = None
            company_name: Optional[str] = None
            contact_email: Optional[EmailStr] = None
            contact_person: Optional[str] = None

        result = await extraction_agent.run(evaluation_prompt, output_model=ExtractedInfo)
        extracted_data: ExtractedInfo = result.data

        if extracted_data and extracted_data.is_suitable and extracted_data.company_name:
            logfire.info(f"WebCrawlAgent: {url_to_crawl} deemed SUITABLE. Company: {extracted_data.company_name}")
            return CompanyInfo(
                company_name=extracted_data.company_name,
                website_url=url_to_crawl,
                contact_email=extracted_data.contact_email,
                contact_person=extracted_data.contact_person,
                reason_for_suitability=extracted_data.reason_for_suitability,
                raw_scraped_data=scraped_data_text[:500] # Store a snippet
            )
        else:
            logfire.info(f"WebCrawlAgent: {url_to_crawl} deemed UNSUITABLE or info incomplete. Reason: {extracted_data.reason_for_suitability if extracted_data else 'No data extracted'}")
            return None
    except Exception as e:
        logfire.error(f"WebCrawlAgent: LLM extraction failed for {url_to_crawl}: {e}")
        return None

# 3. Gmail Agent
async def gmail_agent_logic(
    company_info: CompanyInfo,
    sponsorship_context: SponsorshipInquiryContext,
    mcp_servers: List[MCPServer]
) -> Optional[EmailDraft]:
    """
    Sastavi tekst maila i napravi draft na Gmailu.
    """
    logfire.info(f"GmailAgent: Preparing draft for {company_info.company_name} ({company_info.contact_email or 'No email found'})")

    if not company_info.contact_email:
        logfire.warn(f"GmailAgent: No contact email found for {company_info.company_name}. Cannot create draft.")
        return None

    email_subject = f"Sponsorship Inquiry: {sponsorship_context.event_description}"
    email_body_prompt = f"""
    Compose a sponsorship inquiry email.
    My Event: {sponsorship_context.event_description}
    Event Location: {sponsorship_context.event_location}
    Company Name: {company_info.company_name}
    Company Website: {company_info.website_url}
    Contact Person (if known): {company_info.contact_person or 'Hiring Manager or Marketing Team'}
    Reason they might be interested (if known): {company_info.reason_for_suitability or f'Their focus on {sponsorship_context.target_sponsor_type} aligns with our event.'}

    The email should be polite, concise, and clearly state the sponsorship request.
    Ask if they are interested in learning more.
    My (the sender's) name is [Your Name/Organization Name] - replace this.
    My contact email is [Your Email] - replace this.
    """

    try:
        mail_composer_agent = Agent(
            model=llm_model,
            system_prompt="You are an expert marketing assistant that writes compelling sponsorship inquiry emails.",
        )
        # For simplicity, getting text. You could have a Pydantic model for the email content.
        result = await mail_composer_agent.run(email_body_prompt)
        composed_body: str = result.data # Assuming result.data is the string of the email body

        # Replace placeholders - IMPORTANT
        final_body = composed_body.replace("[Your Name/Organization Name]", "AI Sponsorship Seeker Bot") # TODO: Make this configurable
        final_body = final_body.replace("[Your Email]", "your.email@example.com") # TODO: Make this configurable

        draft = EmailDraft(
            recipient_email=company_info.contact_email,
            recipient_name=company_info.contact_person,
            subject=email_subject,
            body=final_body,
            company_url=company_info.website_url
        )

        # --- Call Gmail MCP Server to create draft ---
        # gmail_mcp = next((s for s in mcp_servers if "gmail" in s.id_or_url_or_cmd), None) # Conceptual
        # if gmail_mcp:
        #     draft_creation_payload = {
        #         "to": str(draft.recipient_email),
        #         "subject": draft.subject,
        #         "body": draft.body,
        #         # Any other params the Gmail MCP server expects
        #     }
        #     response = await gmail_mcp.call_method("create_draft", **draft_creation_payload)
        #     if response.get("success"):
        #         logfire.info(f"GmailAgent: Successfully created draft for {company_info.company_name} to {draft.recipient_email}. Draft ID: {response.get('draft_id')}")
        #         return draft
        #     else:
        #         logfire.error(f"GmailAgent: Failed to create draft via MCP. Response: {response}")
        #         return None # Or maybe return the draft object anyway for manual sending
        # else:
        #     logfire.warn("Gmail MCP server not configured. Draft not sent to Gmail.")
        #     # For now, we'll return the draft object so the user can see it.
        logfire.info(f"GmailAgent: Draft composed for {company_info.company_name}. (Gmail MCP call skipped in this example).")
        print("\n--- DRAFT EMAIL ---")
        print(f"To: {draft.recipient_name} <{draft.recipient_email}>")
        print(f"Subject: {draft.subject}")
        print("---")
        print(draft.body)
        print("--- END DRAFT ---\n")
        return draft

    except Exception as e:
        logfire.error(f"GmailAgent: Error composing or drafting email for {company_info.company_name}: {e}")
        return None


# --- Main Workflow Orchestration ---
class SponsorshipWorkflow:
    def __init__(self, sponsorship_context: SponsorshipInquiryContext, mcp_servers_list: List[MCPServer]):
        self.sponsorship_context = sponsorship_context
        self.processed_urls = {} # In-memory cache for this run; replace with MCP Memory Server
        self.mcp_servers = mcp_servers_list

        # Initialize MCP server clients if PydanticAI doesn't manage them globally via Agent context
        # self.memory_client = MemoryMCPClient(find_mcp_server_by_id_or_cmd(mcp_servers_list, MEMORY_MCP_SERVER_COMMAND))
        # self.firecrawl_client = FirecrawlMCPClient(...)
        # self.gmail_client = GmailMCPClient(...)

        # For this example, we'll simulate memory with a dict and direct calls for MCP interactions
        # In a real PydanticAI setup, these would be calls through the mcp_server objects passed to agents
        # or by creating an Agent with specific tools mapped to these MCPs.

    async def _get_url_status_from_memory(self, url: HttpUrl) -> Optional[UrlMemoryEntry]:
        # SIMULATE MCP Memory GET
        # In real usage:
        # response = await self.memory_client.get(str(url))
        # return UrlMemoryEntry(**response) if response else None
        return self.processed_urls.get(str(url))

    async def _store_url_status_to_memory(self, entry: UrlMemoryEntry):
        # SIMULATE MCP Memory SET
        # In real usage:
        # await self.memory_client.set(str(entry.url), entry.model_dump_json())
        logfire.info(f"Memory: Storing {entry.url} with status {entry.status}")
        self.processed_urls[str(entry.url)] = entry


    async def run(self):
        logfire.info("Starting sponsorship workflow.")

        # 1. Agent za websearch
        logfire.info("--- Step 1: Web Search Agent ---")
        # In a full PydanticAI agent, you might do:
        # search_agent = Agent(model=llm_model, system_prompt="You are a web search specialist.", mcp_servers=self.mcp_servers, tools=[DuckDuckGoTool()])
        # search_results_response = await search_agent.run(
        #     f"Find 20 websites for: {self.sponsorship_context.model_dump_json()}",
        #     output_model=List[SearchedUrl]
        # )
        # found_urls = search_results_response.data
        found_urls: List[SearchedUrl] = await web_search_agent_logic(self.sponsorship_context, self.mcp_servers)

        if not found_urls:
            logfire.warn("No URLs found by WebSearchAgent. Exiting.")
            return

        logfire.info(f"Found {len(found_urls)} potential URLs.")
        drafts_created = []

        # 2. Loopa kroz listu i proslijedi agentu za webcrawl
        logfire.info("\n--- Step 2 & 3: Web Crawl & Email Draft Agents Loop ---")
        for i, searched_url_obj in enumerate(found_urls):
            url = searched_url_obj.url
            logfire.info(f"Processing URL {i+1}/{len(found_urls)}: {url}")

            # Provjeri u memoriji
            memory_entry = await self._get_url_status_from_memory(url)
            if memory_entry:
                logfire.info(f"URL {url} already processed. Status: {memory_entry.status}")
                if memory_entry.status == "suitable_contacted" and memory_entry.company_info:
                     # Optionally, add to a list of already contacted if needed for review
                    pass
                continue # Skip if already processed satisfactorily or unsuitably

            await self._store_url_status_to_memory(UrlMemoryEntry(url=url, status="pending_crawl"))

            # Agent za webcrawl
            company_data: Optional[CompanyInfo] = await web_crawl_agent_logic(url, self.sponsorship_context, self.mcp_servers)

            if company_data:
                logfire.info(f"Company data extracted for {company_data.company_name} from {url}")
                await self._store_url_status_to_memory(UrlMemoryEntry(url=url, status="suitable_contacted", company_info=company_data))

                # 3. Proslijedi agentu za Gmail
                email_draft: Optional[EmailDraft] = await gmail_agent_logic(company_data, self.sponsorship_context, self.mcp_servers)
                if email_draft:
                    drafts_created.append(email_draft)
                    logfire.info(f"Email draft created for {company_data.company_name}")
                    # Memory should reflect that a draft was made for this company/URL
                    # The current UrlMemoryEntry already covers this by status="suitable_contacted" and storing company_info
                else:
                    logfire.warn(f"Failed to create email draft for {company_data.company_name}")
                    # Optionally update memory to reflect draft failure if needed for retry logic
            else:
                logfire.warn(f"No suitable company data extracted from {url} or deemed unsuitable.")
                await self._store_url_status_to_memory(UrlMemoryEntry(url=url, status="unsuitable"))

        # 4. User pregleda draftove
        logfire.info("\n--- Step 4: User Review ---")
        if drafts_created:
            print(f"\n{len(drafts_created)} email drafts have been prepared (and simulated sending/Gmail MCP interaction):")
            for i, draft in enumerate(drafts_created):
                print(f"\n--- Draft {i+1} for {draft.company_url} ---")
                print(f"To: {draft.recipient_name or 'N/A'} <{draft.recipient_email}>")
                print(f"Subject: {draft.subject}")
                print("Body:")
                print(draft.body)
                print("--- End of Draft ---")
            print("\nPlease review these drafts in your Gmail (if MCP server was live and successful) or as printed above.")
            print("You can then send or delete them from Gmail.")
        else:
            print("\nNo email drafts were created in this run.")

        logfire.info("Sponsorship workflow finished.")


async def main_cli():
    print("=== AI Sponsorship Agent ===")
    event_desc = input("Enter a description of your event: ")
    event_loc = input("Enter the location of your event (e.g., Osijek): ")
    sponsor_type = input("What type of sponsors are you looking for? (e.g., bicycle shops, tech companies): ")

    context = SponsorshipInquiryContext(
        event_description=event_desc,
        event_location=event_loc,
        target_sponsor_type=sponsor_type,
    )

    # --- Initialize and Run MCP Servers (if managed by PydanticAI) ---
    # This is a conceptual way to manage MCP servers based on your example.
    # PydanticAI's `Agent.run_mcp_servers()` might be the more direct way if all
    # interactions are through a single top-level PydanticAI Agent.
    # Since we have a multi-agent workflow, managing them explicitly or ensuring
    # PydanticAI can route to them correctly is key.

    # For this example, we are not using agent.run_mcp_servers() because
    # the MCP server commands are placeholders and would require actual npx packages.
    # We are SIMULATING the calls to MCP servers within the agent logic functions.
    # If you have live MCP servers, you'd pass the `mcp_servers_config` to the PydanticAI Agents
    # or use a global context.

    print("\nStarting workflow... (MCP server interactions are currently simulated or use direct libraries)")
    logfire.info("Starting main_cli for SponsorshipWorkflow")

    # In a real PydanticAI setup with MCPServerStdio, you might wrap this
    # in a context manager if PydanticAI provides one for managing server lifecycles
    # when not using the main `Agent.run_mcp_servers()` chat loop.
    #
    # async with some_mcp_lifecycle_manager(mcp_servers_config):
    # workflow = SponsorshipWorkflow(sponsorship_context=context, mcp_servers_list= ACTUAL_MCP_SERVER_OBJECTS)
    # await workflow.run()

    # Since MCP server setup with PydanticAI can be complex and depends on how they are run (stdio, http),
    # this example focuses on the agent logic and data flow.
    # You'll need to integrate the MCPServerStdio or MCPServer instances correctly.
    # For now, we pass an empty list, and agents will use fallbacks or simulated calls.
    active_mcp_servers = [] # Replace with actual initialized MCPServer objects if not using global Agent

    # Example of how you might prepare MCPServerStdio instances if you were to manage them
    # This is highly dependent on PydanticAI's API for this.
    # For MCPServerStdio, PydanticAI usually handles the lifecycle if you pass them to an Agent's constructor.
    # If running them independently, you'd manage their subprocesses.

    # Let's assume for this script, the MCP server instances are configured and passed.
    # If PydanticAI's Agent handles their startup/shutdown when passed in `mcp_servers`,
    # you might not need explicit start/stop here for each agent, but ensure they are part of
    # a PydanticAI Agent's context or passed around.

    # The example you provided for Agent chat loop uses `agent.run_mcp_servers()`.
    # For a scripted workflow like this, the setup might be slightly different.
    # You might need to start servers if PydanticAI doesn't do it automatically
    # when MCPServerStdio instances are merely created.

    # Simplified for this example:
    print("NOTE: This script uses simulated MCP interactions or direct library calls (like duckduckgo_search).")
    print("Full MCP server integration requires running the npx commands for memory, firecrawl, and gmail servers,")
    print("and configuring PydanticAI to connect to them correctly.")

    workflow = SponsorshipWorkflow(sponsorship_context=context, mcp_servers_list=active_mcp_servers)
    await workflow.run()


if __name__ == "__main__":
    # If running in Jupyter or an environment with an active event loop:
    # import nest_asyncio
    # nest_asyncio.apply()
    try:
        asyncio.run(main_cli())
    except KeyboardInterrupt:
        print("\nWorkflow interrupted by user.")
    finally:
        logfire.info("Application shutdown.")