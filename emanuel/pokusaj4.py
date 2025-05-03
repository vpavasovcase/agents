import os
import asyncio
from dotenv import load_dotenv
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerStdio
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider
from docx import Document
import pdfplumber
import pandas as pd

# Učitavanje environment varijabli
load_dotenv(override=True)

# Provjera da li je API ključ postavljen
if not os.getenv('OPENAI_API_KEY'):
    raise ValueError("OPENAI_API_KEY nije postavljen u environment varijablama")

# Konfiguracija MCP servera
servers = [
    MCPServerStdio('npx', ['-y', '@pydantic/mcp-run-python', 'stdio']),
    MCPServerStdio('npx', ['-y', '@modelcontextprotocol/server-filesystem', '.'])
]

# Kreiranje OpenAI modela
model = OpenAIModel('gpt-4o', provider=OpenAIProvider(api_key=os.getenv('OPENAI_API_KEY')))

# Kreiranje agenta
agent = Agent(
    model=model,
    system_prompt="You are an AI assistant that helps to fill templates using extracted data from documents.",
    mcp_servers=servers
)

# Funkcije za čitanje različitih tipova dokumenata

def read_docx(file_path):
    """Čitanje Word dokumenta (docx)"""
    doc = Document(file_path)
    text = ""
    for para in doc.paragraphs:
        text += para.text + "\n"
    return text

def read_pdf(file_path):
    """Čitanje PDF dokumenta"""
    with pdfplumber.open(file_path) as pdf:
        text = ""
        for page in pdf.pages:
            text += page.extract_text()
    return text

def read_excel(file_path):
    """Čitanje Excel dokumenta"""
    df = pd.read_excel(file_path)
    return df.to_string()  # Možeš prilagoditi za specifične kolone

# Funkcija za procesuiranje dokumenata
def process_document(file_path, file_type):
    """Procesira dokument prema tipu"""
    if file_type == 'docx':
        return read_docx(file_path)
    elif file_type == 'pdf':
        return read_pdf(file_path)
    elif file_type == 'excel':
        return read_excel(file_path)
    else:
        raise ValueError("Nepodržani tip dokumenta")

# Funkcija za popunjavanje template dokumenta
async def fill_template():
    print("=== Agent za popunjavanje dokumenta ===")
    print("Agent će analizirati template dokument i popuniti ga sa podacima iz drugih dokumenata.")
    print("Tip 'exit' za završetak.")
    print("===============================")
    
    # Povijest razgovora
    conversation_history = []
    
    # Pokretanje MCP servera
    async with agent.run_mcp_servers():
        try:
            initial_message = """
            I need to fill the template_dodatciugovoru.docx with data from other documents.
            Analyze the template and identify the fields to be filled.
            Extract data from the provided documents and fill the template accordingly.
            """
            result = await agent.run(initial_message, message_history=conversation_history)
            print('[Assistant] ', result.output)
            conversation_history = result.all_messages()
            
            while True:
                user_input = input("\n[You] ")
                
                if user_input.lower() in ['exit', 'quit', 'bye']:
                    print("Goodbye!")
                    break
                
                try:
                    result = await agent.run(user_input, message_history=conversation_history)
                    print('[Assistant] ', result.output)
                    conversation_history = result.all_messages()
                except Exception as e:
                    print(f"\nError: {e}")

        except Exception as e:
            print(f"\nError during template processing: {e}")

# Pozivanje glavne funkcije
if __name__ == '__main__':
    asyncio.run(fill_template())
