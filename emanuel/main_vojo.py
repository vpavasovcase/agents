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
from pydantic_ai import Agent, ModelRetry, Tool, RunContext, AllTools
from pydantic_ai.models.groq import GroqModel
from pydantic_ai.mcp import MCPServerStdio
import logfire
from PIL import Image
import pytesseract
from pdf2image import convert_from_path
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Logfire
logfire.configure()

# Set base directory
ROOT_DIR = Path("/app/docs").resolve()

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

# Context for agent with MCP servers
class AgentContext(BaseModel):
    credit_number: str
    mcp_enabled: bool = True

# Tools
async def process_pdf_with_ocr(ctx: RunContext[AgentContext], file_path: str) -> str:
    """Process PDF files and extract text via OCR if needed"""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    logger.info(f"Processing PDF: {path}")
    
    # First try to extract text directly
    try:
        import PyPDF2
        with open(path, 'rb') as file:
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
    images = convert_from_path(str(path))
    
    full_text = ""
    for i, image in enumerate(images):
        # Save temporary image
        temp_image_path = path.parent / f"temp_{path.stem}_page_{i+1}.png"
        image.save(str(temp_image_path), "PNG")
        
        # Perform OCR
        text = pytesseract.image_to_string(
            str(temp_image_path), 
            lang='hrv+eng',  # Croatian + English
            config='--psm 6'  # Uniform text block
        )
        full_text += text + "\n\n"
        
        # Clean up
        temp_image_path.unlink()
    
    return full_text

async def extract_data_patterns(ctx: RunContext[AgentContext], text: str, field_type: str) -> Optional[str]:
    """Extract specific data from text using patterns"""
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

# MCP Servers configuration
mcp_servers: List[MCPServerStdio] = [
    MCPServerStdio("npx", ["-y", "@modelcontextprotocol/server-filesystem", ROOT_DIR.as_posix()]),
    MCPServerStdio("uvx", ["--from", "office-word-mcp-server", "word_mcp_server"]),
]

# Create Groq model
model = GroqModel(
    'llama-3.2-90b-vision-preview',
    api_key=os.getenv('GROQ_API_KEY')
)

# System prompt
system_prompt = """You are an expert loan agreement processor for Croatian bank HPB (Hrvatska Poštanska Banka).
Your task is to extract data from credit documents and fill out loan agreement amendments.

You understand Croatian banking terminology and can handle both Croatian and English documents.
You are meticulous about data accuracy and always verify extracted information.
When data is ambiguous or missing, you clearly communicate what's needed from the user.

You have access to MCP tools for filesystem operations and Word document manipulation.
Use these tools to:
1. List and read files in the source directories
2. Analyze the template document structure
3. Fill the template with extracted data

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

# Create agent with MCP servers
agent = Agent(
    model=model,
    system_prompt=system_prompt,
    tools=[
        Tool(process_pdf_with_ocr, description="Process PDF files and extract text via OCR if needed"),
        Tool(extract_data_patterns, description="Extract specific data fields from text using patterns"),
        *AllTools(),  # Include all MCP tools
    ],
    result_type=LoanAgreement,
    mcp_servers=mcp_servers,
    deps_type=AgentContext,
)

# Instrument the agent for Logfire
Agent.instrument_all()

# Main workflow
class LoanAgreementProcessor:
    """Main processor orchestrating the workflow"""
    
    def __init__(self):
        self.agent = agent
        self.base_path = ROOT_DIR
        
    async def process_credit_documents(self, credit_number: str) -> LoanAgreement:
        """Process all documents for a credit number and extract loan data"""
        
        # Create context
        context = AgentContext(credit_number=credit_number)
        
        # Build the prompt for the agent
        prompt = f"""
        Process loan agreement for credit number: {credit_number}
        
        Steps to follow:
        1. Use the filesystem MCP tool to list files in /app/docs/sources/{credit_number}/
        2. Read and analyze all PDF documents found
        3. Extract all relevant information for the loan agreement amendment
        4. Use the Word MCP tool to analyze the template at /app/docs/template.docx
        5. Identify which fields need to be filled based on the template structure
        6. Validate all extracted data
        7. Return a complete LoanAgreement object with all required information
        
        If any critical information is missing, ask the user for clarification.
        Pay special attention to:
        - Credit user details (name, address, OIB)
        - Credit numbers and amounts
        - Dates and locations
        - Whether this is an ex-NHB credit
        - Whether there was HRK to EUR conversion
        """
        
        # Run agent with retry logic
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                result = await self.agent.run(prompt, deps=context)
                return result.data
                
            except ModelRetry as e:
                retry_count += 1
                # Ask user for missing information
                missing_info = await self.get_missing_info_from_user(e.message)
                if missing_info:
                    prompt += f"\n\nAdditional information from user:\n{missing_info}"
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
        """Fill the template with loan data using MCP Word server"""
        
        context = AgentContext(credit_number=loan_data.credit_info.credit_number)
        
        # Prepare replacement mappings
        replacements = self.prepare_replacements(loan_data)
        
        # Create prompt for filling the template
        fill_prompt = f"""
        Fill the loan agreement template with the following data:
        
        1. Use the Word MCP tool to copy /app/docs/template.docx to /app/docs/completed/{loan_data.credit_info.credit_number}.docx
        2. Replace all placeholders in the document with the actual values:
        
        {self.format_replacements_for_prompt(replacements)}
        
        3. Handle conditional sections:
           - If this is an ex-NHB credit, keep the merger introduction paragraph
           - If this is not an ex-NHB credit, remove the merger paragraph
           - If payment schedule changes, use the appropriate text variant
        
        4. Save the completed document
        5. Return the path to the completed document
        """
        
        result = await self.agent.run(fill_prompt, deps=context, result_type=str)
        
        output_path = self.base_path / "completed" / f"{loan_data.credit_info.credit_number}.docx"
        return output_path
    
    def prepare_replacements(self, loan_data: LoanAgreement) -> Dict[str, str]:
        """Prepare replacement mappings for the template"""
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
        }
        
        # Add EUR conversion if applicable
        if loan_data.credit_info.is_hrk_converted:
            eur_amount = loan_data.credit_info.original_amount / 7.53450
            replacements.update({
                "IZNOS_KREDITA": f"{eur_amount:,.2f}",
                "IZNOS_SL": self.amount_to_words(eur_amount),
            })
        
        # Add payment information if available
        if loan_data.payment_amount:
            replacements["[XX.XXX,XX]"] = f"{loan_data.payment_amount:,.2f}"
            
        if loan_data.new_monthly_payment:
            replacements["[XX.XXX,XX]"] = f"{loan_data.new_monthly_payment:,.2f}"
        
        return replacements
    
    def format_replacements_for_prompt(self, replacements: Dict[str, str]) -> str:
        """Format replacements for the agent prompt"""
        lines = []
        for placeholder, value in replacements.items():
            lines.append(f"   - Replace '{placeholder}' with '{value}'")
        return "\n".join(lines)
    
    def date_to_words(self, date_str: str) -> str:
        """Convert date to Croatian words"""
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
        words = {
            1: "jedan", 2: "dva", 3: "tri", 4: "četiri", 5: "pet",
            6: "šest", 7: "sedam", 8: "osam", 9: "devet", 10: "deset",
            11: "jedanaest", 12: "dvanaest", 13: "trinaest", 14: "četrnaest",
            15: "petnaest", 16: "šesnaest", 17: "sedamnaest", 18: "osamnaest",
            19: "devetnaest", 20: "dvadeset", 30: "trideset"
        }
        
        if num in words:
            return words[num]
        elif 20 < num < 30:
            return f"dvadeset {words[num-20]}"
        elif 30 < num < 40:
            return f"trideset {words[num-30]}"
        else:
            return str(num)
    
    def amount_to_words(self, amount: float) -> str:
        """Convert amount to Croatian words (simplified)"""
        # This is a simplified version
        # In production, use a proper number-to-words library
        whole = int(amount)
        decimal = int((amount - whole) * 100)
        
        result = f"{self.number_to_thousands_words(whole)} eura"
        if decimal > 0:
            result += f" i {decimal}/100"
        
        return result
    
    def number_to_thousands_words(self, num: int) -> str:
        """Convert larger numbers to words (simplified)"""
        if num < 1000:
            return self.number_to_words(num)
        
        thousands = num // 1000
        remainder = num % 1000
        
        result = ""
        if thousands == 1:
            result = "tisuću"
        elif thousands < 5:
            result = f"{self.number_to_words(thousands)} tisuće"
        else:
            result = f"{self.number_to_words(thousands)} tisuća"
            
        if remainder > 0:
            result += f" {self.number_to_words(remainder)}"
            
        return result
    
    async def run(self, credit_number: str):
        """Main workflow execution"""
        try:
            logger.info(f"Starting processing for credit: {credit_number}")
            
            # 1. Extract loan data from documents
            loan_data = await self.process_credit_documents(credit_number)
            logger.info("Data extraction completed")
            
            # 2. Validate data
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
            
            # 3. Fill template
            output_path = await self.fill_template(loan_data)
            logger.info(f"✅ Document completed: {output_path}")
            
            print(f"\n✅ Success! Document saved to: {output_path}")
            print(f"\nExtracted loan data summary:")
            print(f"  - Credit User: {loan_data.credit_user.name}")
            print(f"  - Credit Number: {loan_data.credit_info.credit_number}")
            print(f"  - Amendment Number: {loan_data.amendment_number}")
            print(f"  - Amendment Date: {loan_data.amendment_date}")
            
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

if __name__ == "__main__":
    asyncio.run(main())