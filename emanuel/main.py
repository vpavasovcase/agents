import asyncio
import os
from dotenv import load_dotenv
import logfire
from pydantic import BaseModel, Field
from typing import Optional, List, Dict

from pydantic_ai import Agent, DocumentUrl, BinaryContent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.mcp import MCPServerStdio
from pydantic_ai.providers.openai import OpenAIProvider
from datetime import datetime

# Load environment variables from .env file (useful for local testing, Docker handles this)
load_dotenv(override=True)

# --- Logfire Setup ---
# Ispravljena konfiguracija za Logfire Pydantic plugin
logfire.configure() # Osnovna konfiguracija
logfire.instrument_pydantic() # Instrumentiraj Pydantic modele
logfire.info("Agent started")

# --- Folder Structure (adjust as needed for your Docker mapping) ---
DOCS_BASE_PATH = os.getenv('DOCS_BASE_PATH', '/app/emanuel/docs') 

def get_credit_sources_path(credit_number: str) -> str:
    return os.path.join(DOCS_BASE_PATH, 'sources', credit_number)

def get_completed_doc_path(credit_number: str) -> str:
    return os.path.join(DOCS_BASE_PATH, 'completed', f'{credit_number}.docx')

def get_template_doc_path() -> str:
    return os.path.join(DOCS_BASE_PATH, 'template.docx')

def get_template_pdf_path() -> str:
    return os.path.join(DOCS_BASE_PATH, 'template.pdf') # Optional

# --- Pydantic Models ---
class Participant(BaseModel):
    ime_prezime: str = Field(..., description="Ime i prezime sudionika (Korisnik kredita, Solidarni dužnik, Solidarni jamac).")
    adresa: str = Field(..., description="Adresa sudionika.")
    oib: str = Field(..., description="OIB sudionika.")
    zastupan_po: Optional[str] = Field(None, description="Ime i prezime osobe koja zastupa Solidarnog jamca, ako je primjenjivo.")

class ContractData(BaseModel):
    korisnik_kredita: Participant = Field(..., description="Podaci o Korisniku kredita.")
    solidarni_duznik: str = "Ne"
    solidarni_jamci: str = "Ne"
    datum_dodatka_ddmmyyyy: str = datetime.today().strftime('%d.%m.%Y')

    datum_dodatka_slovima: str = Field(..., description="Datum zaključenja Dodatka ispisan slovima.")
    mjesto_dodatka: str = Field(..., description="Mjesto zaključenja Dodatka.")
    broj_dodatka: int = Field(..., description="Redni broj Dodatka Ugovoru.")
    naziv_ugovora: str = Field(..., description="Naziv osnovnog Ugovora, npr. 'o nenamjenskom kreditu'.")
    broj_ugovora: str = Field(..., description="Broj osnovnog Ugovora (broj kreditne partije).")
    iznos_smanjenja_glavnice: Optional[float] = Field(None, description="Iznos u EUR za smanjenje nedospjele glavnice, ako je primjenjivo (Članak 2, opcija 1).")
    iznos_smanjenja_glavnice_slovima: Optional[str] = Field(None, description="Iznos smanjenja nedospjele glavnice ispisan slovima, ako je primjenjivo (Članak 2, opcija 1).")
    preostala_glavnica: Optional[float] = Field(None, description="Preostali iznos nedospjele glavnice u EUR nakon smanjenja, ako je primjenjivo (Članak 2, opcija 1).")
    preostala_glavnica_slovima: Optional[str] = Field(None, description="Preostali iznos nedospjele glavnice ispisan slovima, ako je primjenjivo (Članak 2, opcija 1).")
    novi_mjesecni_anuitet: Optional[float] = Field(None, description="Novi iznos mjesečnog anuiteta u EUR.")
    novi_mjesecni_anuitet_slovima: Optional[str] = Field(None, description="Novi iznos mjesečnog anuiteta ispisan slovima.")
    clanak_2_option: Optional[int] = Field(None, description="Which option in Članak 2 is applicable? 1 or 2. If not clear from documents, agent should ask user.")

class MissingDataQuestion(BaseModel):
    question: str = Field(..., description="Pitanje za korisnika o podacima koji nedostaju ili zahtijevaju pojašnjenje.")
    field_name: str = Field(..., description="Naziv polja iz ContractData modela na koje se pitanje odnosi.")
    options: Optional[List[str]] = Field(None, description="Opcije za odabir, ako je pitanje višestrukog izbora (npr. za uvjete iz Članka 2).")

class AgentResponse(BaseModel):
    status: str = Field(..., description="Status agentovog zadatka ('success', 'missing_data', 'error').")
    data_to_fill: Optional[ContractData] = Field(None, description="Ekstrahirani i popunjeni podaci spremni za umetanje u template.")
    question_to_user: Optional[MissingDataQuestion] = Field(None, description="Pitanje za korisnika ako podaci nedostaju ili zahtijevaju pojašnjenje.")
    message: str = Field(..., description="Poruka korisniku o statusu zadatka.")

# --- MCP Servers ---
# Make sure these servers are accessible from within your Docker container
# The filesystem server root needs to be configured to access your 'docs' folder
servers = [
    MCPServerStdio('npx', ['-y', '@pydantic/mcp-run-python', 'stdio']),
    # Assume the docs folder is mounted at /app/docs in the container
    MCPServerStdio('npx', ['-y', '@modelcontextprotocol/server-filesystem', DOCS_BASE_PATH]),
    # Office Word MCP Server using uvx
    MCPServerStdio( 'uvx', ['--from', 'office-word-mcp-server', 'word_mcp_server'] ),
]

# --- Agent Definition ---
model = OpenAIModel('gpt-4.1-mini', provider=OpenAIProvider(api_key=os.getenv('OPENAI_API_KEY')))

system_prompt = f"""
You are a banking document automation agent. Your primary task is to fill out a standard bank document template (Dodatak Ugovoru) using data extracted from other source documents provided for a specific credit number.

You will be given a command like "Popuni mi predložak [broj_kredita]".
Your workflow is as follows:
1.  Identify the credit number from the user's command.
2.  Locate the source documents for this credit number in the directory: `{DOCS_BASE_PATH}/sources/[broj_kredita]`. Use the `filesystem.read_directory` tool to list files in this directory.
3.  Locate the template document: `{DOCS_BASE_PATH}/template.docx`.
4.  Locate the optional template PDF for reference: `{DOCS_BASE_PATH}/template.pdf`.
5.  Analyze the template document (`template.docx` and potentially `template.pdf` for comments/hints) to understand which fields need to be populated. Pay close attention to placeholders like [IME I PREZIME], [XX.XXX,XX], [upisati slovima iznos], etc.
6.  Read the content of all source documents found in the credit number's source folder. Use tools like `filesystem.read` for text-based files (like PDFs if they are text-searchable) or potentially specialized tools for Word/Excel if needed.
7.  Extract the necessary data points identified in step 5 from the source documents. Look for information like:
    * Korisnik kredita details (Ime, Prezime, Adresa, OIB). Look in credit agreements, account statements, etc.
    * Solidarni dužnik/jamac details.
    * Credit agreement number (broj ugovora/partije). This should match the credit number from the user's command.
    * Details about the loan (naziv ugovora/vrsta kredita).
    * Financial figures (iznos kredita, iznos smanjenja glavnice, preostala glavnica, mjesečni anuitet). Look in loan agreements, repayment plans (otplatni plan), account statements.
    * Dates and places related to the original contract and the amendment.
    * Information about which condition in Članak 2 applies (e.g., is there a principal reduction?).
8.  Populate the `ContractData` Pydantic model with the extracted information.
9.  If you cannot find a required piece of information, or if there are conditional fields (like in Članak 2) where the applicable condition is not clear from the documents, use the `MissingDataQuestion` Pydantic model to ask the user for clarification. Respond with an `AgentResponse` with status 'missing_data' and the question.
10. If you have successfully extracted all required information or received it from the user, prepare the `ContractData` model.
11. Use the Office Word MCP server tool (`officeword.fill_template`) to create a new `.docx` document based on the template (`template.docx`) and the extracted data. You will need to provide the template path, the output path (`{DOCS_BASE_PATH}/completed/[broj_kredita].docx`), and a dictionary of placeholders and their values based on your `ContractData`.
12. Save the completed document if the officeword tool requires it, using `filesystem.write` if necessary.
13. Respond with an `AgentResponse` with status 'success' and a message indicating the document has been created. If there was an error, respond with status 'error'.

**Important Considerations:**
* When asking the user for clarification, provide enough context from the documents or the template so they can understand the question.
* Be precise when using tool calls. Refer to the documentation for the filesystem and officeword MCP servers for exact command names and parameters.
* Use Logfire to log your steps and any issues encountered.
* Datum zaključenja Dodatka ispisan slovima i datum zaključenja dodatka u formatu DD.MM.GGGG. treba biti današnji datum, koristi mcp server run_python za dobiti datum.
* opcija iz članka 2 primjenjiva za svaki dodatak je opcija 1, a to je smanjenje glavnice.
* glavnica prije smanjenja: 9.158,10 EUR , glavnica nakon smanjenja: 6.158,10 EUR.
* Prema novom "Otplatnom planu" (Otplatni_plan.pdf), "Iznos obroka ili anuiteta u EUR" je 185,26 EUR. Slovima: sto osamdeset pet eura i dvadeset šest centi.
Begin by processing the user's command and attempting to extract the credit number.
"""

agent = Agent(
    model=model,
    system_prompt=system_prompt,
    mcp_servers=servers
)


# --- Main CLI Loop ---
async def main():
    print("=== Bank Document Agent ===")
    print("Type 'exit', 'quit', or 'bye' to end the conversation")
    print("============================")

    conversation_history = []
    current_credit_number: Optional[str] = None # Specify type hint
    missing_data_fields: Dict[str, Optional[List[str]]] = {} # To track which fields are missing and need user input

    async with agent.run_mcp_servers():
        logfire.info("MCP Servers are running.")
        while True:
            user_input = input("\n[You] ")

            if user_input.lower() in ['exit', 'quit', 'bye', 'goodbye']:
                print("Goodbye!")
                break

            agent_task = None # Reset agent_task for each loop iteration

            # Basic command parsing for "Popuni mi predložak [broj_kredita]"
            if user_input.lower().startswith("popuni mi predložak"):
                parts = user_input.split()
                if len(parts) == 4 and parts[0].lower() == "popuni" and parts[1].lower() == "mi" and parts[2].lower() == "predložak":
                    current_credit_number = parts[3]
                    print(f"Ok, attempting to fill the template for credit number: {current_credit_number}")
                    # Clear previous missing data questions for a new task
                    missing_data_fields = {}
                    # Postavi agent_task samo ako je current_credit_number uspješno postavljen
                    agent_task = f"Process the request to fill the template for credit number {current_credit_number}. Find source documents in {get_credit_sources_path(current_credit_number)}, use template {get_template_doc_path()}, and save the output to {get_completed_doc_path(current_credit_number)}. Use the defined Pydantic models for responses."
                else:
                    print("Invalid command format. Please use 'Popuni mi predložak [broj_kredita]'.")

            elif missing_data_fields and current_credit_number is not None: # Dodana provjera da current_credit_number nije None
                # User is providing input for missing data
                logfire.info("Processing user input for missing data.")
                # Ova logika za obradu korisničkog unosa za nedostajuće podatke je i dalje pojednostavljena
                # Trebat će vam robusniji mehanizam ovisno o tome kako agent postavlja pitanja
                if len(missing_data_fields) == 1:
                     field_name = list(missing_data_fields.keys())[0]
                     agent_task = f"The user provided the value '{user_input}' for the missing field '{field_name}'. Continue filling the document for credit number {current_credit_number}."
                     missing_data_fields = {} # Clear the pending question after getting input
                else:
                    # Ako ima više pitanja koja čekaju odgovor, možda treba specifičan format unosa
                    print("Please provide the requested information.")
                    agent_task = None # Čekaj na specifičan unos ako je potrebno

            elif current_credit_number is None: # Handle cases where no credit number is set yet
                 print("Please start by telling me which template to fill, e.g., 'Popuni mi predložak 1234567890'.")
                 agent_task = None # No task to run

            # Pokreni agenta samo ako je agent_task postavljen
            if agent_task:
                try:
                    result = await agent.run(
                        agent_task,
                        message_history=conversation_history,
                        output_type=AgentResponse
                    )
                    logfire.info("Agent run completed.", response=result.output)

                    # Process the structured response
                    if result.output.status == 'success':
                        print(f"[Assistant] {result.output.message}")
                        # Putanja za spremljeni dokument se sada dohvaća unutar ove grane, nakon uspjeha
                        # i osigurano je da current_credit_number nije None
                        if current_credit_number is not None:
                             print(f"Completed document saved to: {get_completed_doc_path(current_credit_number)}")
                        current_credit_number = None # Task completed, reset credit number
                    elif result.output.status == 'missing_data':
                        print(f"[Assistant] {result.output.message}")
                        # Sigurno pristupi atributima jer provjeravamo question_to_user is not None dolje
                        if result.output.question_to_user is not None:
                            print(f"Missing data: {result.output.question_to_user.question}")
                            # Store the missing data field to know what the next user input is for
                            missing_data_fields[result.output.question_to_user.field_name] = result.output.question_to_user.options
                        else:
                             logfire.error("Agent returned missing_data status but no question_to_user.")
                             print("[Assistant] Error: Agent indicated missing data but did not provide a question.")
                             current_credit_number = None # Error occurred, reset credit number

                    elif result.output.status == 'error':
                        print(f"[Assistant] Error: {result.output.message}")
                        current_credit_number = None # Error occurred, reset credit number
                    else:
                         logfire.warning(f"Agent returned unexpected status: {result.output.status}")
                         print(f"[Assistant] Received unexpected status: {result.output.status}. Message: {result.output.message}")
                         current_credit_number = None # Treat as error, reset credit number


                    # Store the messages from this interaction in the conversation history
                    conversation_history = result.all_messages()

                except Exception as e:
                    logfire.error("An error occurred during agent execution.", exc_info=True)
                    print(f"\nError: {e}")
                    current_credit_number = None # Error occurred, reset credit number

if __name__ == '__main__':
    # Ensure the necessary directories exist
    os.makedirs(os.path.join(DOCS_BASE_PATH, 'sources'), exist_ok=True)
    os.makedirs(os.path.join(DOCS_BASE_PATH, 'completed'), exist_ok=True)

    print(f"Document base path set to: {DOCS_BASE_PATH}")
    print("Please ensure your 'sources', 'completed', and 'template.docx/pdf' folders are correctly placed within this path.")
    print("\nExample command: Popuni mi predložak 9919479387")


    asyncio.run(main())