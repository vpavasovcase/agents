"""
Sponsor Agent System - Main Workflow Controller

This script coordinates the multi-agent workflow for finding and contacting potential sponsors:
1. Search Agent finds potential sponsor companies
2. Crawl Agent analyzes websites for suitability
3. Gmail Agent creates email drafts for suitable companies

All agents use a memory system to track processed URLs.
"""

import os
import asyncio
from typing import List, Optional
from pydantic import BaseModel

# Import agents
from search_agent import WebSearchAgent
from crawl_agent import WebCrawlAgent
from gmail_agent import GmailAgent

# Import memory system
from memory_system import MemoryClient

# Configure logging


class CompanyData(BaseModel):
    """Structure for company data extracted from websites"""
    name: str
    website_url: str
    description: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    phone: Optional[str] = None
    relevance_score: float = 0.0
    notes: Optional[str] = None

async def main():
    """Run the main sponsorship workflow"""
    
    # Initialize the event details (customize these for your event)
    event_name = "Biciklistička utrka Osijek 2025"
    event_date = "15. srpnja 2025"
    event_location = "Osijek, Hrvatska"
    event_description = "Godišnja biciklistička utrka kroz grad Osijek s više od 500 sudionika."
    search_query = "prodavaonice bicikala Osijek Hrvatska"
    
    logger.info(f"Starting sponsor search for event: {event_name}")
    
    # Initialize memory client
    memory = MemoryClient()
    
    # Initialize agents
    search_agent = WebSearchAgent(memory_client=memory)
    crawl_agent = WebCrawlAgent(memory_client=memory)
    gmail_agent = GmailAgent(memory_client=memory)
    
    # Step 1: Find potential sponsor companies
    logger.info(f"Searching for potential sponsors with query: {search_query}")
    potential_urls = await search_agent.search(
        query=search_query,
        num_results=20
    )
    logger.info(f"Found {len(potential_urls)} potential websites")
    
    # Step 2: Process each URL
    for url in potential_urls:
        # Check if URL was already processed
        if await memory.has_processed_url(url):
            logger.info(f"Skipping already processed URL: {url}")
            continue
        
        # Extract company data
        logger.info(f"Crawling website: {url}")
        company_data = await crawl_agent.crawl(url)
        
        # Mark URL as processed
        await memory.mark_url_processed(url)
        
        # If company is not suitable, continue to next URL
        if not company_data or company_data.relevance_score < 0.6:
            logger.info(f"Company not suitable for sponsorship: {url}")
            continue
        
        # Step 3: Create email draft for suitable companies
        logger.info(f"Creating email draft for: {company_data.name}")
        email_result = await gmail_agent.create_draft(
            company_data=company_data,
            event_name=event_name,
            event_date=event_date,
            event_location=event_location,
            event_description=event_description
        )
        
        if email_result.success:
            logger.info(f"Email draft created successfully for {company_data.name}")
        else:
            logger.error(f"Failed to create email draft for {company_data.name}: {email_result.error}")
    
    logger.info("Sponsorship workflow completed")

if __name__ == "__main__":
    asyncio.run(main())
