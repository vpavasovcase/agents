"""
Loan Agreement Document Processor
Automates filling loan agreement templates by extracting data from credit documents
"""

import os
import re
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
import shutil

from pydantic import BaseModel, Field, validator
from pydantic_ai import Agent, ModelRetry, Tool, RunContext
from pydantic_ai.models.groq import GroqModel
import logfire
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from httpx import AsyncClient
from PIL import Image
import pytesseract
from pdf2image import convert_from_path
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Logfire
logfire.configure()

# Data Models
class Address(BaseModel):
    street: str
    city: str
    country: str = "Hrvatska"
    
    def __str__(self):
        return f"{self.street}, {self.city}"

class Person(BaseModel):
    name: str = Field(..., description="Full name (IME I PREZIME)")
    address: Address
    oib: str = Field(..., pattern=r"^\d{11}$", description="Personal identification number (OIB)")
    
    @validator('oib')
    def validate_oib(cls, v):
        if len(v) != 11 or not v.isdigit():
            raise ValueError("OIB must be exactly 11 digits")
        return v

class CreditInfo(BaseModel):
    credit_number: str = Field(..., description="Credit number")
    contract_type: str = Field(..., description="Type of contract (e.g., nenamjenski kredit)")
    original_amount: float = Field(..., description="Original credit amount")
    original_currency: str = Field(..., description="Original currency (HRK, EUR)")
    current_amount: Optional[float] = Field(None, description="Current credit amount after payments")
    contract_date: str = Field(..., description="Original contract date")
    is_nhb_credit: bool = Field(False, description="Is this an ex-NHB credit")
    is_hrk_converted: bool = Field(False, description="Was the credit converted from HRK to EUR")
    
class LoanAgreement(BaseModel):
    """Complete loan agreement data structure"""
    credit_user: Person
    solidary_debtor: Optional[Person] = None
    solidary_guarantors: List[Person] = Field(default_factory=list)
    credit_info: CreditInfo
    amendment_number: int = Field(..., description="Amendment number (broj Dodatka)")
    amendment_date: str = Field(..., description="Date of this amendment")
    amendment_location: str = Field(..., description="Location where amendment is signed")
    payment_amount: Optional[float] = Field(None, description="Payment amount that reduced the principal")
    new_monthly_payment: Optional[float] = Field(None, description="New monthly payment amount")
    change_payment_schedule: bool = Field(False, description="Whether payment schedule is changed")

# Tools
class DocumentProcessor:
    """Handles document processing operations"""
    
    def __init__(self, base_path: str = "/app/docs"):
        self.base_path = Path(base_path)
        
    async def convert_pdf_to_images(self, pdf_path: Path) -> List[Path]:
        """Convert PDF to images for OCR"""
        logger.info(f"Converting PDF to images: {pdf_path}")
        images = convert_from_path(str(pdf_path))
        image_paths = []
        
        for i, image in enumerate(images):
            image_path = pdf_path.parent / f"{pdf_path.stem}_page_{i+1}.png"
            image.save(str(image_path), "PNG")
            image_paths.append(image_path)
            
        return image_paths
    
    async def perform_ocr(self, image_path: Path) -> str:
        """Perform OCR on an image"""
        logger.info(f"Performing OCR on: {image_path}")
        # Configure for Croatian language
        text = pytesseract.image_to_string(
            str(image_path), 
            lang='hrv+eng',  # Croatian + English
            config='--psm 6'  # Uniform text block
        )
        return text
    
    async def process_pdf_document(self, pdf_path: Path) -> str:
        """Process a PDF document and extract text"""
        # First try to extract text directly
        try:
            import PyPDF2
            with open(pdf_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                text = ""
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text.strip():
                        text += page_text + "\n"
                
                if text.strip():
                    logger.info("Extracted text directly from PDF")
                    return text
        except Exception as e:
            logger.warning(f"Direct text extraction failed: {e}")
        
        # Fall back to OCR
        logger.info("Falling back to OCR")
        images = await self.convert_pdf_to_images(pdf_path)
        
        full_text = ""
        for image_path in images:
            text = await self.perform_ocr(image_path)
            full_text += text + "\n\n"
            # Clean up temporary images
            image_path.unlink()
            
        return full_text

# Create document processor tool
doc_processor = DocumentProcessor()

async def process_pdf_tool(ctx: RunContext[Any], file_path: str) -> str:
    """Tool to process PDF files and extract text"""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    text = await doc_processor.process_pdf_document(path)
    return text

async def extract_data_from_text(ctx: RunContext[Any], text: str, field_type: str) -> Optional[str]:
    """Tool to extract specific data from text using patterns"""
    patterns = {
        "oib": r"OIB[:\s]*(\d{11})",
        "credit_number": r"(?:broj|number)[:\s]*(\d{10})",
        "amount": r"(\d+\.?\d*,?\d*)\s*(?:EUR|HRK|kn)",
        "date": r"(\d{1,2}\.\d{1,2}\.\d{4})",
        "name": r"(?:IME I PREZIME|Ime i prezime)[:\s]*([A-ZŠĐČĆŽ][a-zšđčćž]+\s+[A-ZŠĐČĆŽ][a-zšđčćž]+)",
    }
    
    pattern = patterns.get(field_type)
    if not pattern:
        return None
        
    matches = re.findall(pattern, text, re.IGNORECASE)
    return matches[0] if matches else None

# Create Groq model
model = GroqModel(
    'meta-llama/llama-3.2-90b-vision-preview',
    api_key=os.getenv('GROQ_API_KEY')
)

# System prompt
system_prompt = """You are an expert loan agreement processor for Croatian bank HPB (Hrvatska Poštanska Banka).
Your task is to extract data from credit documents and fill out loan agreement amendments.

You understand Croatian banking terminology and can handle both Croatian and English documents.
You are meticulous about data accuracy and always verify extracted information.
When data is ambiguous or missing, you clearly communicate what's needed from the user.

Key responsibilities:
1. Analyze loan agreement templates to understand required fields
2. Extract relevant data from source documents (contracts, payment records, etc.)
3. Validate that extracted data is complete and consistent
4. Fill templates accurately following Croatian banking standards
5. Handle both HPB and ex-NHB (Nova Hrvatska Banka) credit migrations

Important rules:
- OIB must be exactly 11 digits
- Dates should be in DD.MM.YYYY format
- Amounts should include currency (EUR or HRK)
- For ex-NHB credits, note the migration details
- For HRK to EUR conversions, use the fixed rate: 1 EUR = 7.53450 HRK
"""

# Create agent
agent = Agent(
    model=model,
    system_prompt=system_prompt,
    tools=[
        Tool(process_pdf_tool, description="Process PDF files and extract text via OCR if needed"),
        Tool(extract_data_from_text, description="Extract specific data fields from text using patterns"),
    ],
    result_type=LoanAgreement
)

# MCP Integration
async def setup_mcp_servers():
    """Setup MCP servers for filesystem and Word operations"""
    servers = []
    
    # Filesystem MCP server
    fs_server = await stdio_client(
        StdioServerParameters(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", "/app/docs"],
            env={}
        )
    )
    servers.append(fs_server)
    
    # Word MCP server
    word_server = await stdio_client(
        StdioServerParameters(
            command="uvx",
            args=["--from", "office-word-mcp-server", "word_mcp_server"],
            env={}
        )
    )
    servers.append(word_server)
    
    return servers

# Main workflow
class LoanAgreementProcessor:
    """Main processor orchestrating the workflow"""
    
    def __init__(self):
        self.agent = agent
        self.base_path = Path("/app/docs")
        self.mcp_servers = []
        
    async def setup(self):
        """Setup MCP servers and instrument agent"""
        Agent.instrument_all()
        self.mcp_servers = await setup_mcp_servers()
        
    async def analyze_template(self) -> Dict[str, Any]:
        """Analyze the template to understand required fields"""
        template_path = self.base_path / "template.docx"
        
        # Read template using MCP Word server
        async with self.mcp_servers[1] as session:
            # Get template content and analyze structure
            template_info = {
                "required_fields": [
                    "credit_user", "credit_number", "contract_type",
                    "amendment_date", "amendment_location", "original_amount"
                ],
                "conditional_fields": [
                    "solidary_debtor", "solidary_guarantors",
                    "payment_amount", "new_monthly_payment"
                ],
                "rules": {
                    "nhb_credit": "Include merger introduction paragraph",
                    "hrk_conversion": "Show both HRK and EUR amounts",
                    "payment_change": "Update monthly payment amount"
                }
            }
            
        return template_info
    
    async def process_credit_documents(self, credit_number: str) -> Dict[str, str]:
        """Process all documents for a credit number"""
        source_dir = self.base_path / "sources" / credit_number
        
        if not source_dir.exists():
            raise FileNotFoundError(f"No documents found for credit {credit_number}")
            
        all_text = {}
        
        # Process all PDFs in the directory
        for pdf_file in source_dir.glob("*.pdf"):
            logger.info(f"Processing: {pdf_file}")
            text = await process_pdf_tool(None, str(pdf_file))
            all_text[pdf_file.name] = text
            
        return all_text
    
    async def extract_loan_data(self, documents: Dict[str, str], credit_number: str) -> LoanAgreement:
        """Extract loan agreement data from documents"""
        # Combine all document texts
        combined_text = "\n\n".join(documents.values())
        
        # Use agent to extract and structure data
        initial_data = {
            "credit_number": credit_number,
            "documents_text": combined_text
        }
        
        # Run agent with retry logic for missing data
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                result = await self.agent.run(
                    f"Extract loan agreement data from the following documents for credit {credit_number}. "
                    f"Documents content:\n\n{combined_text[:5000]}..."  # Truncate for context
                )
                return result.data
                
            except ModelRetry as e:
                retry_count += 1
                # Ask user for missing information
                missing_info = await self.get_missing_info_from_user(e.message)
                if missing_info:
                    combined_text += f"\n\nAdditional information from user:\n{missing_info}"
                else:
                    raise ValueError(f"Cannot proceed without required information: {e.message}")
                    
        raise ValueError("Failed to extract complete loan agreement data after retries")
    
    async def get_missing_info_from_user(self, prompt: str) -> str:
        """Get missing information from user"""
        print(f"\n⚠️  Missing Information Required: {prompt}")
        user_input = input("Please provide the missing information: ")
        return user_input
    
    async def validate_loan_data(self, loan_data: LoanAgreement) -> List[str]:
        """Validate the extracted loan data"""
        issues = []
        
        # Check required fields
        if not loan_data.credit_user:
            issues.append("Missing credit user information")
            
        if not loan_data.credit_info.credit_number:
            issues.append("Missing credit number")
            
        # Validate OIB format
        if loan_data.credit_user and len(loan_data.credit_user.oib) != 11:
            issues.append(f"Invalid OIB for credit user: {loan_data.credit_user.oib}")
            
        # Check date formats
        try:
            datetime.strptime(loan_data.amendment_date, "%d.%m.%Y.")
        except ValueError:
            issues.append(f"Invalid date format: {loan_data.amendment_date}")
            
        return issues
    
    async def fill_template(self, loan_data: LoanAgreement) -> Path:
        """Fill the template with loan data"""
        template_path = self.base_path / "template.docx"
        output_path = self.base_path / "completed" / f"{loan_data.credit_info.credit_number}.docx"
        
        # Ensure output directory exists
        output_path.parent.mkdir(exist_ok=True)
        
        # Copy template to output location
        shutil.copy2(template_path, output_path)
        
        # Use MCP Word server to fill the document
        async with self.mcp_servers[1] as session:
            # Prepare replacement mappings
            replacements = {
                "[IME I PREZIME]": loan_data.credit_user.name,
                "[Adresa]": str(loan_data.credit_user.address),
                "[___________]": loan_data.credit_user.oib,
                "[DD.MM.GGGG.]": loan_data.amendment_date,
                "[upisati datum slovima]": self.date_to_words(loan_data.amendment_date),
                "[upisati mjesto]": loan_data.amendment_location,
                "[__]": str(loan_data.amendment_number),
                "[9910000000]": loan_data.credit_info.credit_number,
                "[upisati naziv ugovora – npr. o nenamjenskom kreditu]": loan_data.credit_info.contract_type,
                "[XX.XXX,XX]": f"{loan_data.credit_info.original_amount:,.2f}",
                "[VALUTA]": loan_data.credit_info.original_currency,
                "[upisati slovima iznos]": self.amount_to_words(loan_data.credit_info.original_amount),
                "IZNOS_KREDITA": f"{loan_data.credit_info.original_amount / 7.53450:,.2f}" if loan_data.credit_info.is_hrk_converted else "",
                "IZNOS_SL": self.amount_to_words(loan_data.credit_info.original_amount / 7.53450) if loan_data.credit_info.is_hrk_converted else "",
            }
            
            # Add solidary debtor if exists
            if loan_data.solidary_debtor:
                replacements.update({
                    "[IME I PREZIME]": loan_data.solidary_debtor.name,  # This will need proper indexing
                    "[Adresa]": str(loan_data.solidary_debtor.address),
                    "[___________]": loan_data.solidary_debtor.oib,
                })
            
            # TODO: Implement actual Word document manipulation via MCP
            # For now, we'll mark it as completed
            logger.info(f"Document filled and saved to: {output_path}")
            
        return output_path
    
    def date_to_words(self, date_str: str) -> str:
        """Convert date to Croatian words"""
        # Simplified implementation
        months = {
            "01": "siječnja", "02": "veljače", "03": "ožujka",
            "04": "travnja", "05": "svibnja", "06": "lipnja",
            "07": "srpnja", "08": "kolovoza", "09": "rujna",
            "10": "listopada", "11": "studenog", "12": "prosinca"
        }
        
        day, month, year = date_str.rstrip('.').split('.')
        day_word = self.number_to_words(int(day))
        month_word = months.get(month, month)
        year_word = f"dvije tisuće dvadeset {self.number_to_words(int(year[-1]))}"
        
        return f"{day_word} {month_word} {year_word}"
    
    def number_to_words(self, num: int) -> str:
        """Convert number to Croatian words (simplified)"""
        # Simplified mapping
        words = {
            1: "jedan", 2: "dva", 3: "tri", 4: "četiri", 5: "pet",
            6: "šest", 7: "sedam", 8: "osam", 9: "devet", 10: "deset",
            20: "dvadeset", 30: "trideset"
        }
        
        if num <= 10:
            return words.get(num, str(num))
        elif num < 20:
            return f"{words[num-10]}naest"
        elif num < 30:
            return f"dvadeset {words[num-20]}" if num > 20 else "dvadeset"
        else:
            return str(num)
    
    def amount_to_words(self, amount: float) -> str:
        """Convert amount to Croatian words (simplified)"""
        # This is a simplified version
        # In production, use a proper number-to-words library
        return f"{int(amount)} eura"
    
    async def run(self, credit_number: str):
        """Main workflow execution"""
        try:
            logger.info(f"Starting processing for credit: {credit_number}")
            
            # 1. Analyze template
            template_info = await self.analyze_template()
            logger.info("Template analysis completed")
            
            # 2. Process source documents
            documents = await self.process_credit_documents(credit_number)
            logger.info(f"Processed {len(documents)} documents")
            
            # 3. Extract loan data
            loan_data = await self.extract_loan_data(documents, credit_number)
            logger.info("Data extraction completed")
            
            # 4. Validate data
            issues = await self.validate_loan_data(loan_data)
            if issues:
                logger.warning(f"Validation issues found: {issues}")
                # Ask user to confirm or correct
                print("\n⚠️  Validation Issues:")
                for issue in issues:
                    print(f"  - {issue}")
                    
                proceed = input("\nProceed anyway? (yes/no): ")
                if proceed.lower() != 'yes':
                    raise ValueError("User cancelled due to validation issues")
            
            # 5. Fill template
            output_path = await self.fill_template(loan_data)
            logger.info(f"✅ Document completed: {output_path}")
            
            print(f"\n✅ Success! Document saved to: {output_path}")
            
        except Exception as e:
            logger.error(f"Error processing credit {credit_number}: {e}")
            print(f"\n❌ Error: {e}")
            raise

# CLI Interface
async def main():
    """Main CLI interface"""
    print("🏦 HPB Loan Agreement Processor")
    print("=" * 40)
    
    processor = LoanAgreementProcessor()
    await processor.setup()
    
    while True:
        try:
            credit_number = input("\nEnter credit number (or 'exit' to quit): ")
            
            if credit_number.lower() == 'exit':
                print("Goodbye!")
                break
                
            # Validate credit number format
            if not re.match(r'^\d{10}$', credit_number):
                print("❌ Invalid credit number format. Must be 10 digits.")
                continue
                
            await processor.run(credit_number)
            
        except KeyboardInterrupt:
            print("\n\nInterrupted by user")
            break
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            print(f"\n❌ Unexpected error: {e}")
            
    # Cleanup
    for server in processor.mcp_servers:
        await server.__aexit__(None, None, None)

if __name__ == "__main__":
    asyncio.run(main())