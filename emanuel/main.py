import asyncio
import os
import sys
from dotenv import load_dotenv
import logfire
from pydantic import BaseModel, Field
from typing import Optional, List, Dict

from pydantic_ai import Agent, DocumentUrl, BinaryContent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.mcp import MCPServerStdio
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.providers.deepseek import DeepSeekProvider
from pydantic_ai.models.groq import GroqModel
from pydantic_ai.providers.groq import GroqProvider
from datetime import datetime

# Load environment variables from .env file (useful for local testing, Docker handles this)
load_dotenv(override=True)

# --- Logfire Setup ---
logfire.configure()
logfire.instrument_pydantic()
logfire.info("Agent started")
Agent.instrument_all()

# --- Folder Structure (adjust as needed for your Docker mapping) ---
DOCS_BASE_PATH = os.getenv('DOCS_BASE_PATH', '/app/emanuel/docs') 

def get_credit_sources_path(credit_number: str) -> str:
    return os.path.join(DOCS_BASE_PATH, 'sources', credit_number)

def get_completed_doc_path(credit_number: str) -> str:
    return os.path.join(DOCS_BASE_PATH, 'completed', f'{credit_number}.docx')

def get_template_doc_path() -> str:
    return os.path.join(DOCS_BASE_PATH, 'template.docx')

def get_template_pdf_path() -> str:
    return os.path.join(DOCS_BASE_PATH, 'template.pdf')

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
    document_path: Optional[str] = Field(None, description="Putanja do spremljenog dokumenta, ako je uspješno generiran.")

# Define specific tools for document processing
class WordTools(BaseModel):
    async def fill_template(self, template_path: str, output_path: str, data: Dict) -> str:
        """
        Fill a Word template with the given data and save to output path
        """
        # This will be implemented by the MCP server - just a stub for typing
        return output_path
    
    async def save_document(self, document_path: str) -> bool:
        """
        Explicitly save the document at the given path
        """
        # This will be implemented by the MCP server - just a stub for typing
        return True

# --- MCP Servers ---
servers = [
    MCPServerStdio('npx', ['-y', '@pydantic/mcp-run-python', 'stdio']),
    MCPServerStdio('npx', ['-y', '@modelcontextprotocol/server-filesystem', DOCS_BASE_PATH]),
    MCPServerStdio('uvx', ['--from', 'office-word-mcp-server', 'word_mcp_server']),
]

# --- Agent Definition ---
model = GroqModel(
    'llama-3.3-70b-versatile', provider=GroqProvider(api_key=os.getenv('GROQ_API_KEY'))
)

system_prompt = f"""
You are a banking document automation agent specialized in filling out the 'Dodatak Ugovoru' template. Your primary task is to use the provided source documents for a specific credit number to extract all necessary information and then use the Office Word MCP server to fill and save the template document.

Your workflow is strictly defined as follows:
1.  Receive a command from the user requesting to fill the template for a specific credit number, e.g., "Popuni mi predložak [broj_kredita]".
2.  Identify the credit number from the command.
3.  Acknowledge the request and the credit number you will process.
4.  Locate the directory containing source documents for this credit number. The path pattern is: `{DOCS_BASE_PATH}/sources/[broj_kredita]`. You will replace '[broj_kredita]' with the actual credit number provided by the user. Use the filesystem.list_directory tool to see available files in that specific directory.
5.  Locate the template document: `{DOCS_BASE_PATH}/template.docx`.
6.  (Optional but recommended) Locate the template reference PDF: `{DOCS_BASE_PATH}/template.pdf` if available, to understand structure or notes.
7.  Analyze the `template.docx` to identify all placeholders or fields that need to be populated (e.g., [IME I PREZIME], [ADRESA], [OIB], [BROJ UGOVORA], [IZNOS], [IZNOS SLOVIMA], [DATUM], [MJESTO], [ČLANAK 2 OPCIJA], etc.).
8.  Read the content of the source documents found in the specific credit number's source folder (as identified in step 4). Use appropriate tools like filesystem.read for text files, or other specialized tools if available for specific document types.
9.  Extract all the required data points identified in step 7 from the source documents. Pay close attention to details for:
    * Korisnik kredita (Ime, Prezime, Adresa, OIB).
    * Solidarni dužnik/jamac details (and whether they exist).
    * Basic contract details (broj ugovora - this should match the credit number, naziv ugovora/vrsta kredita).
    * Financial details related to the amendment (iznos smanjenja glavnice before and after, preostala glavnica, novi mjesečni anuitet). Ensure you get both numerical and text representations if required by the template, converting numbers to words if necessary.
    * Dates and places (datum i mjesto zaključenja originalnog ugovora, mjesto zaključenja dodatka). The 'Datum zaključenja Dodatka' should be today's date (format DD.MM.YYYY and slovima). 
    * Identify which option within Članak 2 of the template is applicable based on the source documents (e.g., if a principal reduction occurred).
10. Populate the `ContractData` Pydantic model with *all* the extracted information.
11. **CRITICAL STEP:** If *any* required data point is missing or ambiguous (especially regarding conditional sections like Članak 2 if not clearly specified in docs), use the `MissingDataQuestion` Pydantic model to ask the user for the specific missing information, providing context. Respond with an `AgentResponse` with `status='missing_data'`. *Do not proceed to document filling until all necessary data is confirmed.*
12. If all data is successfully extracted and confirmed (either from documents or user input):
    * For this example, since we don't have actual source documents, create a mock ContractData object with placeholder values
    * Return an AgentResponse with status='success' and include the document_path
13. Upon successful creation and saving of the document, respond with an `AgentResponse` with `status='success'`, document_path set to the saved file path, and a message confirming completion and the save location.
14. If an error occurs at any stage, respond with an `AgentResponse` with `status='error'` and a description of the problem.

**Important: In this initial implementation, do not attempt to directly call the Office Word MCP server functions yet.** Instead, return a success response with a mock ContractData and document_path until we verify the basic functionality works.

For the initial test with credit number 9919479387, return a success response with:
- status: "success"
- message: "Template filled and saved successfully"
- document_path: "{DOCS_BASE_PATH}/completed/9919479387.docx"
- data_to_fill: A placeholder ContractData object with basic values

This will help us verify that the agent can communicate properly before we implement the full document processing functionality.
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

    # Add dependency check
    try:
        import docx
        print("python-docx library is available - will create proper Word documents")
    except ImportError:
        print("Warning: python-docx library is not installed. Document creation will be limited.")
        print("To enable full functionality, install with: pip install python-docx")

    conversation_history = []
    current_credit_number: Optional[str] = None
    missing_data_fields: Dict[str, Optional[List[str]]] = {}

    async with agent.run_mcp_servers():
        logfire.info("MCP Servers are running.")
        
        # Add debug info to verify Office Word MCP server is running
        try:
            # Check if the MCP servers are accessible
            for server in servers:
                if "office-word-mcp-server" in str(server):
                    logfire.info("Office Word MCP server appears to be configured.")
        except Exception as e:
            logfire.error(f"Error checking MCP servers: {e}", exc_info=True)
        
        while True:
            user_input = input("\n[You] ")

            if user_input.lower() in ['exit', 'quit', 'bye', 'goodbye']:
                print("Goodbye!")
                break

            agent_task = None

            # Basic command parsing for "Popuni mi predložak [broj_kredita]"
            if user_input.lower().startswith("popuni mi predložak"):
                parts = user_input.split()
                if len(parts) == 4 and parts[0].lower() == "popuni" and parts[1].lower() == "mi" and parts[2].lower() == "predložak":
                    current_credit_number = parts[3]
                    print(f"Ok, attempting to fill the template for credit number: {current_credit_number}")
                    
                    # Check if source directory exists
                    source_dir = get_credit_sources_path(current_credit_number)
                    if not os.path.exists(source_dir):
                        print(f"Warning: Source directory {source_dir} does not exist.")
                        logfire.warning(f"Source directory {source_dir} does not exist.")
                        # Create the directory for testing purposes
                        os.makedirs(source_dir, exist_ok=True)
                        print(f"Created source directory for testing: {source_dir}")
                    
                    # Check if template exists
                    template_path = get_template_doc_path()
                    if not os.path.exists(template_path):
                        print(f"Error: Template file {template_path} does not exist.")
                        logfire.error(f"Template file {template_path} does not exist.")
                        # For initial testing, we can continue even without the template
                        print("Continuing with simulation mode for testing...")
                    
                    # Clear previous missing data questions for a new task
                    missing_data_fields = {}
                    
                    # Create completed directory if it doesn't exist
                    completed_dir = os.path.join(DOCS_BASE_PATH, 'completed')
                    os.makedirs(completed_dir, exist_ok=True)
                    
                    # Create a valid Word document skeleton instead of just an empty file
                    output_path = get_completed_doc_path(current_credit_number)
                    try:
                        # Import required libraries for creating a valid Word document
                        from docx import Document
                        
                        # Create a basic Word document with some content
                        doc = Document()
                        doc.add_heading(f'Dodatak Ugovoru za kredit: {current_credit_number}', 0)
                        doc.add_paragraph(f'Ovo je test dokument generiran za broj kredita: {current_credit_number}')
                        doc.add_paragraph('Ovo je privremeni dokument za testiranje funkcionalnosti.')
                        
                        # Add a table with example data
                        table = doc.add_table(rows=3, cols=2)
                        table.style = 'Table Grid'
                        
                        # Add headers
                        cell = table.cell(0, 0)
                        cell.text = "Polje"
                        cell = table.cell(0, 1)
                        cell.text = "Vrijednost"
                        
                        # Add some sample data
                        cell = table.cell(1, 0)
                        cell.text = "Broj kredita"
                        cell = table.cell(1, 1)
                        cell.text = current_credit_number
                        
                        cell = table.cell(2, 0)
                        cell.text = "Datum kreiranja"
                        cell = table.cell(2, 1)
                        cell.text = datetime.today().strftime('%d.%m.%Y')
                        
                        # Save the document
                        doc.save(output_path)
                        print(f"Created valid Word document: {output_path}")
                    except ImportError:
                        print("Warning: python-docx package is not installed. Creating simple text file instead.")
                        try:
                            # Fallback to creating a simple XML file that Word might be able to open
                            with open(output_path, 'w', encoding='utf-8') as f:
                                f.write('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n')
                                f.write('<w:document xmlns:w="http://schemas.microsoft.com/office/word/2003/wordml">\n')
                                f.write('  <w:body>\n')
                                f.write(f'    <w:p><w:r><w:t>Test document for credit number: {current_credit_number}</w:t></w:r></w:p>\n')
                                f.write('    <w:p><w:r><w:t>This is a test document.</w:t></w:r></w:p>\n')
                                f.write('  </w:body>\n')
                                f.write('</w:document>')
                            print(f"Created simple XML document: {output_path}")
                        except Exception as e:
                            print(f"Warning: Could not create test document: {e}")
                    except Exception as e:
                        print(f"Warning: Could not create test document: {e}")
                    
                    agent_task = f"""Process the request to fill the template for credit number {current_credit_number}. 
                    In this test implementation, you do not need to actually process any documents.
                    Just simulate the process and return a successful AgentResponse with:
                    - status: 'success'
                    - message: 'Template filled and saved successfully'
                    - document_path: '{get_completed_doc_path(current_credit_number)}'
                    """
                else:
                    print("Invalid command format. Please use 'Popuni mi predložak [broj_kredita]'.")

            elif missing_data_fields and current_credit_number is not None:
                # User is providing input for missing data
                logfire.info("Processing user input for missing data.")
                if len(missing_data_fields) == 1:
                     field_name = list(missing_data_fields.keys())[0]
                     agent_task = f"The user provided the value '{user_input}' for the missing field '{field_name}'. Continue filling the document for credit number {current_credit_number}."
                     missing_data_fields = {} # Clear the pending question after getting input
                else:
                    print("Please provide the requested information.")
                    agent_task = None

            elif current_credit_number is None:
                 print("Please start by telling me which template to fill, e.g., 'Popuni mi predložak 1234567890'.")
                 agent_task = None

            # Run the agent only if there's a task
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
                        
                        # Verify if document was actually created - make sure current_credit_number is not None
                        if result.output.document_path:
                            doc_path = result.output.document_path
                            if os.path.exists(doc_path):
                                print(f"Document successfully created and saved at: {doc_path}")
                                logfire.info(f"Document successfully created: {doc_path}")
                            else:
                                print(f"Warning: Document was reported as created, but the file doesn't exist at {doc_path}")
                                logfire.warning(f"Document doesn't exist at reported path: {doc_path}")
                        elif current_credit_number is not None:
                            # Fallback if document_path isn't set but we have a credit number
                            doc_path = get_completed_doc_path(current_credit_number)
                            if os.path.exists(doc_path):
                                print(f"Document found at: {doc_path}")
                                logfire.info(f"Document found: {doc_path}")
                            else:
                                print(f"Warning: No document found at expected path: {doc_path}")
                                logfire.warning(f"No document found at expected path: {doc_path}")
                        else:
                            print("Warning: No document path provided and no credit number available")
                            logfire.warning("No document path provided and no credit number available")
                        
                        current_credit_number = None # Task completed, reset credit number
                    elif result.output.status == 'missing_data':
                        print(f"[Assistant] {result.output.message}")
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
    # Check for required packages
    try:
        import pip
        required_packages = ['python-docx']
        for package in required_packages:
            try:
                __import__(package.replace('-', '_'))
                print(f"✓ Package {package} is installed")
            except ImportError:
                print(f"! Package {package} is not installed. Installing now...")
                try:
                    import subprocess
                    subprocess.check_call([sys.executable, "-m", "pip", "install", package])
                    print(f"✓ Successfully installed {package}")
                except Exception as e:
                    print(f"✗ Failed to install {package}: {e}")
                    print(f"  Please install manually with: pip install {package}")
    except Exception as e:
        print(f"Warning: Package management error: {e}")
    
    # Ensure the necessary directories exist
    os.makedirs(os.path.join(DOCS_BASE_PATH, 'sources'), exist_ok=True)
    os.makedirs(os.path.join(DOCS_BASE_PATH, 'completed'), exist_ok=True)

    print(f"Document base path set to: {DOCS_BASE_PATH}")
    print("Please ensure your 'sources', 'completed', and 'template.docx/pdf' folders are correctly placed within this path.")
    print("\nExample command: Popuni mi predložak 9919479387")

    asyncio.run(main())