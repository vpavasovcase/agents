"""
Gmail Agent for Sponsor System

This agent creates email drafts in Gmail for contacting potential sponsors.
Uses an MCP server for Gmail integration.
"""

import os
from typing import Dict, Any, Optional
from pydantic import BaseModel

import logfire
logger = logfire.getLogger("gmail_agent")

from main import CompanyData

class EmailResult(BaseModel):
    """Structure for email creation results"""
    success: bool
    draft_id: Optional[str] = None
    error: Optional[str] = None

class GmailAgent:
    """Agent for creating email drafts in Gmail"""
    
    def __init__(self, memory_client):
        """Initialize the Gmail agent"""
        self.memory_client = memory_client
        self.system_prompt = """
        You are an agent that creates professional email drafts for sponsorship requests.
        
        Create personalized emails that:
        1. Address the specific recipient and their company
        2. Briefly introduce the event and why it's relevant to them
        3. Clearly explain the sponsorship opportunity
        4. Offer specific benefits for sponsors
        5. Request a meeting or call to discuss further
        6. Include contact information
        7. Use professional but friendly language
        
        The email should be concise but compelling, highlighting the mutual benefit
        of the sponsorship.
        """
    
    async def create_draft(
        self, 
        company_data: CompanyData, 
        event_name: str,
        event_date: str,
        event_location: str,
        event_description: str
    ) -> EmailResult:
        """
        Create an email draft in Gmail
        
        Args:
            company_data: Information about the company
            event_name: Name of the event
            event_date: Date of the event
            event_location: Location of the event
            event_description: Description of the event
            
        Returns:
            Result of email draft creation
        """
        logger.info(f"Creating email draft for: {company_data.name}")
        
        if not company_data.contact_email:
            return EmailResult(
                success=False,
                error="No contact email available"
            )
        
        try:
            # Create email content
            subject = f"Sponsorship Opportunity for {event_name}"
            email_body = self._generate_email_content(
                company_data=company_data,
                event_name=event_name,
                event_date=event_date,
                event_location=event_location,
                event_description=event_description
            )
            
            # In a real implementation, use the Gmail MCP Server instead
            # For this example, we're simulating the Gmail API call
            # Sample code for Gmail MCP Server would be:
            # email_result = await GmailMCPServer.create_draft(
            #     to=company_data.contact_email,
            #     subject=subject,
            #     body=email_body
            # )
            
            # Simulate Gmail API for demo purposes
            draft_id = f"draft_{company_data.name.lower().replace(' ', '_')}"
            
            # Store in memory
            await self.memory_client.store_email_draft(
                company_name=company_data.name,
                url=company_data.website_url,
                draft_id=draft_id
            )
            
            logger.info(f"Email draft created with ID: {draft_id}")
            
            return EmailResult(
                success=True,
                draft_id=draft_id
            )
            
        except Exception as e:
            logger.error(f"Error creating email draft: {e}")
            return EmailResult(
                success=False,
                error=str(e)
            )
    
    def _generate_email_content(
        self,
        company_data: CompanyData,
        event_name: str,
        event_date: str,
        event_location: str,
        event_description: str
    ) -> str:
        """
        Generate email content
        
        Args:
            company_data: Information about the company
            event_name: Name of the event
            event_date: Date of the event
            event_location: Location of the event
            event_description: Description of the event
            
        Returns:
            Email body content
        """
        # Contact name with fallback
        contact_name = company_data.contact_name if company_data.contact_name else "Marketing Team"
        
        email_content = f"""
        Poštovani {contact_name},
        
        Moje ime je [Vaše Ime] i organiziram {event_name} koje će se održati {event_date} u {event_location}.
        
        {event_description}
        
        Tražimo sponzore koji bi bili zainteresirani podržati ovaj događaj, a {company_data.name} nam se čini kao idealan partner zbog Vašeg ugleda i povezanosti s našom temom.
        
        Kao sponzor, dobili biste:
        - Vidljivost brenda na svim promotivnim materijalima
        - Prisutnost na društvenim mrežama i u medijima
        - Mogućnost predstavljanja proizvoda/usluga na događaju
        - Povezivanje s potencijalnim kupcima zainteresiranim za Vaše proizvode
        
        Biste li bili zainteresirani za kratak sastanak ili poziv kako bismo razgovarali o detaljima?
        
        Možete me kontaktirati na:
        - Email: [Vaš Email]
        - Tel: [Vaš Broj]
        
        Srdačan pozdrav,
        [Vaše Ime]
        Organizator {event_name}
        """
        
        return email_content
