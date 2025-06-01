"""
Details about what we are building are in emanuel/sys_prompt.md
Loan Agreement Document Processor
Test credit number: 9919479387
Automates filling loan agreement templates by extracting data from credit documents
"""

import os
import re
import asyncio
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime

from pydantic import BaseModel, Field, field_validator
from pydantic_ai import Agent, ModelRetry, Tool
from pydantic_ai.models.groq import GroqModel
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.providers.groq import GroqProvider
from pydantic_ai.mcp import MCPServerStdio
import logfire
import pytesseract
from pdf2image import convert_from_path
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Logfire
logfire.configure()

# Set base directory
ROOT_DIR = Path("/app/emanuel/docs").resolve()

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

    @field_validator('oib')
    @classmethod
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
async def process_pdf_with_ocr(file_path: str) -> str:
    """Process PDF files and extract text via OCR if needed"""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    logger.info(f"Processing PDF: {path}")

    # First try to extract text directly
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(str(path))
        text = ""
        for page_num in range(len(doc)):
            page = doc[page_num]
            page_text = page.get_text()  # type: ignore
            if page_text.strip():
                text += page_text + "\n"
        doc.close()

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

async def extract_data_patterns(text: str, field_type: str) -> Optional[str]:
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
    MCPServerStdio("npx", ["-y", "@modelcontextprotocol/server-filesystem", "/app"]),
    MCPServerStdio("uvx", ["--from", "office-word-mcp-server", "word_mcp_server"]),
]

# model = GroqModel(
#     'llama-3.2-90b-vision-preview',
#     provider=GroqProvider(api_key=os.getenv('GROQ_API_KEY'))
# )
model = OpenAIModel('gpt-4.1-mini', provider=OpenAIProvider(api_key=os.getenv('OPENAI_API_KEY')))

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
- Dates should be in DD.MM.YYYY or DD.MM.YYYY. format
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
    ],
    output_type=LoanAgreement,
    mcp_servers=mcp_servers,
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

        # Step 1: List available documents
        list_prompt = f"""
        Use the filesystem MCP tool to list files in /app/emanuel/docs/sources/{credit_number}/
        Return only the list of files found.
        """

        await self.agent.run(list_prompt)

        # Step 2: Process documents one by one to avoid context overflow

        # Process key documents first (usually the main agreement document)
        key_documents_prompt = f"""
        From the files in /app/emanuel/docs/sources/{credit_number}/, identify and read only the main loan agreement document.
        Extract the following key information:
        - Credit user name, address, and OIB
        - Credit number and original amount
        - Contract type and date
        - Whether this is an ex-NHB credit
        - Whether there was HRK to EUR conversion

        Return the extracted information in a structured format.
        """

        key_data_result = await self.agent.run(key_documents_prompt)

        # Step 3: Process additional documents for amendment-specific information
        amendment_prompt = f"""
        From the remaining files in /app/emanuel/docs/sources/{credit_number}/, extract amendment-specific information:
        - Amendment number and date
        - Amendment location
        - Payment amounts and schedule changes
        - Any solidary debtors or guarantors

        Return the extracted information in a structured format.
        """

        amendment_data_result = await self.agent.run(amendment_prompt)

        # Step 4: Combine and structure the data
        combine_prompt = f"""
        Combine the extracted information into a complete LoanAgreement object:

        Key data: {key_data_result.output}
        Amendment data: {amendment_data_result.output}

        Create a complete LoanAgreement object with all required fields populated.
        If any critical information is missing, indicate what is needed.
        """

        # Run agent with retry logic
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                result = await self.agent.run(combine_prompt)
                return result.output

            except ModelRetry as e:
                retry_count += 1
                # Ask user for missing information
                missing_info = await self.get_missing_info_from_user(e.message)
                if missing_info:
                    combine_prompt += f"\n\nAdditional information from user:\n{missing_info}"
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

        # Check date formats - accept both with and without trailing dot
        date_valid = False
        try:
            # Try format with trailing dot first
            datetime.strptime(loan_data.amendment_date, "%d.%m.%Y.")
            date_valid = True
        except ValueError:
            try:
                # Try format without trailing dot
                datetime.strptime(loan_data.amendment_date, "%d.%m.%Y")
                date_valid = True
            except ValueError:
                pass

        if not date_valid:
            issues.append(f"Invalid date format: {loan_data.amendment_date} (expected DD.MM.YYYY or DD.MM.YYYY.)")

        return issues

    async def fill_template(self, loan_data: LoanAgreement) -> Path:
        """Fill the template with loan data using MCP Word server"""

        # Ensure completed directory exists
        completed_dir = self.base_path / "completed"
        completed_dir.mkdir(exist_ok=True)

        # Prepare replacement mappings
        replacements = self.prepare_replacements(loan_data)

        # Define paths
        template_path = "/app/emanuel/docs/template.docx"
        output_path = f"/app/emanuel/docs/completed/{loan_data.credit_info.credit_number}.docx"

        # Step 1: Copy the template
        copy_prompt = f"""
        Use the copy_document tool to copy the template file from "{template_path}" to "{output_path}".
        """

        await self.agent.run(copy_prompt)

        # Step 2: Replace placeholders one by one to avoid context overflow
        replacement_prompts = []
        for placeholder, value in replacements.items():
            if value:  # Only replace if value is not empty
                prompt = f"""
                Use the search_and_replace tool on the document "{output_path}" to replace:
                - Search for: "{placeholder}"
                - Replace with: "{value}"
                """
                replacement_prompts.append(prompt)

        # Execute replacements in batches to manage context
        batch_size = 5
        for i in range(0, len(replacement_prompts), batch_size):
            batch = replacement_prompts[i:i+batch_size]
            batch_prompt = "Execute the following replacements:\n\n" + "\n\n".join(batch)
            await self.agent.run(batch_prompt)

        # Step 3: Handle conditional content with sophisticated logic
        await self.handle_conditional_paragraphs(loan_data, output_path)

        # Return the path to the completed document
        return Path(output_path)

    async def handle_conditional_paragraphs(self, loan_data: LoanAgreement, output_path: str) -> None:
        """Handle conditional paragraphs based on credit type and conditions"""

        # Step 1: Handle ex-NHB merger introduction paragraph
        await self.handle_nhb_merger_paragraph(loan_data, output_path)

        # Step 2: Handle EUR conversion paragraphs in Article 1
        await self.handle_eur_conversion_paragraphs(loan_data, output_path)

        # Step 3: Handle payment schedule change paragraphs in Article 2
        await self.handle_payment_schedule_paragraphs(loan_data, output_path)

        # Step 4: Handle solidary debtor/guarantor sections
        await self.handle_solidary_participants(loan_data, output_path)

        # Step 5: Handle document copies count
        await self.handle_document_copies(loan_data, output_path)

    async def handle_nhb_merger_paragraph(self, loan_data: LoanAgreement, output_path: str) -> None:
        """Handle the ex-NHB merger introduction paragraph in UVOD section

        Based on template comment TN5:
        - Show only for ex-NHB credits
        - Remove entire UVOD section for HPB credits
        """

        if loan_data.credit_info.is_nhb_credit:
            # Keep the UVOD section and merger paragraph for ex-NHB credits
            conditional_prompt = f"""
            In the document "{output_path}", ensure the UVOD section is present with the merger paragraph.

            The UVOD section should contain the paragraph explaining that Nova hrvatska banka
            (previously Sberbank d.d., previously VOLKSBANK d.d.) was merged with HPB based on
            court decision Tt-23/25802-2 from July 3, 2023.

            This section is required for ex-NHB credits to explain the legal basis for the amendment.
            """
        else:
            # Remove the entire UVOD section for HPB credits
            conditional_prompt = f"""
            In the document "{output_path}", remove the entire UVOD section for HPB credits.

            Remove:
            - The "UVOD" heading
            - The entire paragraph about Nova hrvatska banka merger
            - Any references to "Pripojeno društvo" or court decisions

            For HPB credits, the document should go directly from the parties section to "Članak 1."
            """

        await self.agent.run(conditional_prompt)

    async def handle_eur_conversion_paragraphs(self, loan_data: LoanAgreement, output_path: str) -> None:
        """Handle EUR conversion paragraphs in Article 1

        Based on template comments TN9 and TN10:
        - TN9: Article 1, point 2 - Show only for HPB credits initially approved in HRK
        - TN10: Article 1, point 3 - Show only for ex-NHB credits, remove for HPB credits
        """

        # Article 1, point 2: EUR conversion paragraph (for HPB credits initially in HRK only)
        if not loan_data.credit_info.is_nhb_credit and loan_data.credit_info.is_hrk_converted:
            # Keep point 2 for HPB credits that were converted from HRK to EUR
            eur_conversion_prompt = f"""
            In the document "{output_path}", ensure Article 1, point 2 is present:
            "Ugovorne strane ovog Dodatka br.__ suglasno utvrđuju da je nakon uvođenja EUR-a kao službene valute u Republici Hrvatskoj, Ugovoru dodijeljen novi broj kredita koji sada glasi {loan_data.credit_info.credit_number}."

            This point is required for HPB credits that were initially approved in HRK and converted to EUR.
            """
            await self.agent.run(eur_conversion_prompt)
        else:
            # Remove point 2 for ex-NHB credits or HPB credits that weren't HRK-converted
            remove_eur_prompt = f"""
            In the document "{output_path}", remove Article 1, point 2 that mentions:
            - "nakon uvođenja EUR-a kao službene valute"
            - "dodijeljen novi broj kredita"

            This point should be removed for ex-NHB credits (regardless of currency) or HPB credits not initially in HRK.
            """
            await self.agent.run(remove_eur_prompt)

        # Article 1, point 3: Migration paragraph (for ex-NHB credits only)
        if loan_data.credit_info.is_nhb_credit:
            # Keep point 3 for ex-NHB credits
            migration_prompt = f"""
            In the document "{output_path}", ensure Article 1, point 3 is present:
            "Nadalje, Ugovorne strane suglasno utvrđuju da je nakon pripajanja pravnog prednika Banke Banci, Ugovoru dodijeljen novi broj evidencije kredita koji sada glasi: {loan_data.credit_info.credit_number}"

            This point explains the new credit number assigned after NHB migration to HPB.
            """
            await self.agent.run(migration_prompt)
        else:
            # Remove point 3 for HPB credits
            remove_migration_prompt = f"""
            In the document "{output_path}", remove Article 1, point 3 that mentions:
            - "nakon pripajanja pravnog prednika Banke"
            - "novi broj evidencije kredita"

            This entire point should be completely removed for HPB credits.
            """
            await self.agent.run(remove_migration_prompt)

    async def handle_payment_schedule_paragraphs(self, loan_data: LoanAgreement, output_path: str) -> None:
        """Handle payment schedule change paragraphs in Article 2

        Based on template comments TN11 and TN12:
        - TN11: Show if payment schedule changes (includes due date change)
        - TN12: Show if payment schedule doesn't change
        """

        if loan_data.change_payment_schedule:
            # Keep the paragraph that mentions changing due date
            schedule_change_prompt = f"""
            In the document "{output_path}", ensure Article 2, point 2 includes the payment schedule change version:
            "Mjesečni anuitet na preostali iznos nedospjele glavnice iznosi [XX.XXX,XX] EUR (slovima: [upisati slovima iznos]) te se mijenja datum dospijeća zadnjeg anuiteta sukladno planu otplate kredita."

            Remove the alternative version that doesn't mention due date changes.
            """
        else:
            # Keep the paragraph without due date change
            no_schedule_change_prompt = f"""
            In the document "{output_path}", ensure Article 2, point 2 includes the version without schedule change:
            "Mjesečni anuitet na preostali iznos nedospjele glavnice iznosi [XX.XXX,XX] EUR (slovima: [upisati slovima iznos])."

            Remove the alternative version that mentions changing due dates.
            """
            schedule_change_prompt = no_schedule_change_prompt

        await self.agent.run(schedule_change_prompt)

    async def handle_solidary_participants(self, loan_data: LoanAgreement, output_path: str) -> None:
        """Handle solidary debtor and guarantor sections

        Based on template comments TN1 and TN14:
        - Remove sections for participants that don't exist
        - Update signature section accordingly
        """

        # Handle solidary debtor section
        if not loan_data.solidary_debtor:
            remove_debtor_prompt = f"""
            In the document "{output_path}", remove the solidary debtor sections:
            - Remove the line "IME I PREZIME iz Adresa, OIB: ___________ (dalje: Solidarni dužnik)"
            - Remove the "SOLIDARNI DUŽNIK" signature section at the end
            """
            await self.agent.run(remove_debtor_prompt)

        # Handle solidary guarantors section
        if not loan_data.solidary_guarantors:
            remove_guarantors_prompt = f"""
            In the document "{output_path}", remove the solidary guarantor sections:
            - Remove lines mentioning "Solidarni jamac"
            - Remove the "SOLIDARNI JAMAC" signature sections at the end
            - Remove any legal entity representative sections if present
            """
            await self.agent.run(remove_guarantors_prompt)

    async def handle_document_copies(self, loan_data: LoanAgreement, output_path: str) -> None:
        """Handle document copies count in Article 4

        Based on template comment TN13:
        - Number of copies depends on total participants + 2 for Bank
        """

        # Calculate total participants
        total_participants = 1  # Credit user
        if loan_data.solidary_debtor:
            total_participants += 1
        if loan_data.solidary_guarantors:
            total_participants += len(loan_data.solidary_guarantors)

        total_copies = total_participants + 2  # +2 for Bank
        bank_copies = 2
        participant_copies = total_participants

        # Convert numbers to Croatian words
        total_copies_words = self.number_to_words(total_copies)
        bank_copies_words = self.number_to_words(bank_copies)
        participant_copies_words = self.number_to_words(participant_copies)

        copies_prompt = f"""
        In the document "{output_path}", update Article 4 with the correct number of copies:

        Replace the copies information with:
        "Ovaj Dodatak br.__ je sačinjen u {total_copies} (slovima: {total_copies_words}) istovjetna primjerka od kojih su {bank_copies} (slovima: {bank_copies_words}) primjerka za Banku, a po {participant_copies} (slovima: {participant_copies_words}) primjerak za Korisnika kredita"

        Add participant list if there are additional participants beyond the credit user.
        """

        await self.agent.run(copies_prompt)

    def prepare_replacements(self, loan_data: LoanAgreement) -> Dict[str, str]:
        """Prepare replacement mappings for the template"""

        # Basic replacements for main credit user
        replacements = {
            # Credit user information
            "IME I PREZIME": loan_data.credit_user.name,
            "Adresa": str(loan_data.credit_user.address),
            "___________": loan_data.credit_user.oib,

            # Amendment information
            "[DD.MM.GGGG.]": loan_data.amendment_date,
            "[upisati datum slovima]": self.date_to_words(loan_data.amendment_date),
            "[upisati mjesto]": loan_data.amendment_location,

            # Credit information
            "[9910000000]": loan_data.credit_info.credit_number,
            "[upisati naziv ugovora – npr. o nenamjenskom kreditu]": loan_data.credit_info.contract_type,
            "[upisati naziv ugovora - npr. o nenamjenskom kreditu]": loan_data.credit_info.contract_type,
            "[VALUTA]": loan_data.credit_info.original_currency,

            # Amendment number - handle all variations
            "[__]": str(loan_data.amendment_number),
            "br.__": f"br.{loan_data.amendment_number}",
            "br[2]. __": f"br.{loan_data.amendment_number}",
            "Dodatka br.__": f"Dodatka br.{loan_data.amendment_number}",
        }

        # Handle multiple amount placeholders with different contexts
        original_amount_formatted = f"{loan_data.credit_info.original_amount:,.2f}".replace(",", ".")
        original_amount_words = self.amount_to_words(loan_data.credit_info.original_amount)

        # Add amount-related replacements
        replacements.update({
            "[XX.XXX,XX]": original_amount_formatted,
            "[upisati slovima iznos]": original_amount_words,
        })

        # Add EUR conversion if applicable (for HRK to EUR converted credits)
        if loan_data.credit_info.is_hrk_converted:
            eur_amount = loan_data.credit_info.original_amount / 7.53450
            eur_amount_formatted = f"{eur_amount:,.2f}".replace(",", ".")
            eur_amount_words = self.amount_to_words(eur_amount)

            replacements.update({
                "=IZNOS_KREDITA": eur_amount_formatted,
                "IZNOS_KREDITA": eur_amount_formatted,
                "IZNOS_SL": eur_amount_words,
            })

        # Handle solidary debtor if present
        if loan_data.solidary_debtor:
            # For now, we'll handle this in the template by replacing the second occurrence
            # This would need more sophisticated handling in a production system
            pass

        # Handle solidary guarantors if present
        if loan_data.solidary_guarantors:
            # Similar to solidary debtor, this needs more sophisticated handling
            pass

        # Add payment-specific information if available
        if loan_data.payment_amount:
            payment_formatted = f"{loan_data.payment_amount:,.2f}".replace(",", ".")
            payment_words = self.amount_to_words(loan_data.payment_amount)

            # These will replace specific instances in the payment context
            replacements.update({
                "[XX.XXX,XX]": payment_formatted,  # This will replace the first occurrence
                "[upisati slovima iznos]": payment_words,
            })

        # Add current amount after payment if available
        if loan_data.credit_info.current_amount:
            current_amount_formatted = f"{loan_data.credit_info.current_amount:,.2f}".replace(",", ".")
            current_amount_words = self.amount_to_words(loan_data.credit_info.current_amount)

            # These would need to be handled contextually in the template
            replacements.update({
                "CURRENT_AMOUNT": current_amount_formatted,
                "CURRENT_AMOUNT_WORDS": current_amount_words,
            })

        # Add new monthly payment if available
        if loan_data.new_monthly_payment:
            monthly_payment_formatted = f"{loan_data.new_monthly_payment:,.2f}".replace(",", ".")
            monthly_payment_words = self.amount_to_words(loan_data.new_monthly_payment)

            replacements.update({
                "NEW_MONTHLY_PAYMENT": monthly_payment_formatted,
                "NEW_MONTHLY_PAYMENT_WORDS": monthly_payment_words,
            })

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

            # Start MCP servers and run the workflow within the context
            async with self.agent.run_mcp_servers():
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

                print(f"\n✅ Success! Loan agreement processing completed")
                print(f"\nExtracted loan data summary:")
                print(f"  - Credit User: {loan_data.credit_user.name}")
                print(f"  - Credit Number: {loan_data.credit_info.credit_number}")
                print(f"  - Amendment Number: {loan_data.amendment_number}")
                print(f"  - Amendment Date: {loan_data.amendment_date}")
                print(f"\n📄 Completed document saved to: {output_path}")

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