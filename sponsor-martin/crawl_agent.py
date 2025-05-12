"""
Web Crawl Agent for Sponsor System

This agent crawls websites to extract company information and evaluates 
if they would be suitable sponsors.
"""

import os
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse, urljoin
import re

from pydantic import BaseModel, Field

import logfire
logfire.configure()
Agent.instrument_all()

# Import CompanyData model from main
from main import CompanyData

class WebCrawlAgent:
    """Agent for crawling websites and extracting company information"""
    
    def __init__(self, memory_client):
        """Initialize the crawl agent"""
        self.memory_client = memory_client
        self.system_prompt = """
        You are a specialized web crawler agent that analyzes company websites to:
        1. Extract company information (name, contact details, business focus)
        2. Determine if they would be suitable sponsors for the specified event
        3. Find contact information for sending sponsorship requests
        
        Focus on finding:
        - Company name and description
        - Contact details (especially email addresses)
        - Names of key people/decision makers
        - Company size and relevance to the event
        
        Evaluate if the company would be a good sponsor based on:
        - Relevance to the event theme
        - Size and potential resources for sponsorship
        - Local presence in the event area
        - Previous sponsorships/community involvement if mentioned
        """
    
    async def crawl(self, url: str) -> Optional[CompanyData]:
        """
        Crawl a website and extract company information
        
        Args:
            url: Website URL to crawl
            
        Returns:
            CompanyData if suitable, None if not suitable
        """
        logger.info(f"Crawling website: {url}")
        
        try:
            # Here we would use the FirecrawlMCPServer for actual crawling
            # For this example, we're simulating the crawling and extraction process
            
            # In a real implementation, replace this with actual FirecrawlMCPServer call
            # Sample code for FirecrawlMCPServer would be:
            # crawler_result = await FirecrawlAgent.query(
            #     url=url,
            #     system_prompt=self.system_prompt
            # )
            
            # Simulate crawl for demo purposes
            company_data = await self._simulate_crawl(url)
            
            # Check if company is suitable
            is_suitable = self._evaluate_suitability(company_data)
            
            # Update memory
            await self.memory_client.mark_url_processed(url, suitable=is_suitable)
            
            if is_suitable:
                logger.info(f"Found suitable sponsor: {company_data.name}")
                return company_data
            else:
                logger.info(f"Company not suitable for sponsorship: {url}")
                return None
            
        except Exception as e:
            logger.error(f"Error during crawling: {e}")
            await self.memory_client.mark_url_processed(url, suitable=False)
            return None
    
    def _evaluate_suitability(self, company_data: CompanyData) -> bool:
        """
        Evaluate if a company would be a suitable sponsor
        
        Args:
            company_data: Extracted company information
            
        Returns:
            True if suitable, False otherwise
        """
        # Basic evaluation - in real implementation would be more sophisticated
        if company_data.relevance_score >= 0.6 and company_data.contact_email:
            return True
        return False
    
    async def _simulate_crawl(self, url: str) -> CompanyData:
        """
        Simulate crawling for demonstration purposes
        In a real implementation, this would use the FirecrawlMCPServer
        
        Args:
            url: Website URL
            
        Returns:
            Extracted company data
        """
        # Extract domain as company name
        domain = urlparse(url).netloc
        company_name = domain.split('.')[0].capitalize()
        
        if "bike" in domain or "bicycle" in domain or "sport" in domain:
            relevance = 0.9
        elif "shop" in domain or "store" in domain:
            relevance = 0.7
        else:
            relevance = 0.4
        
        # Create simulated company data
        return CompanyData(
            name=f"{company_name} Ltd",
            website_url=url,
            description=f"{company_name} is a company specializing in bicycles and sporting equipment.",
            contact_name="John Doe" if relevance > 0.6 else None,
            contact_email=f"info@{domain}" if relevance > 0.6 else None,
            relevance_score=relevance,
            notes="Found contact page with email address" if relevance > 0.6 else "No contact information found"
        )
    
    async def extract_contact_info(self, html_content: str) -> Dict[str, str]:
        """
        Extract contact information from HTML content
        
        Args:
            html_content: HTML content of the page
            
        Returns:
            Dictionary with contact information
        """
        contact_info = {}
        
        # Extract email addresses
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        emails = re.findall(email_pattern, html_content)
        if emails:
            contact_info['email'] = emails[0]
        
        # Extract phone numbers (simplified pattern)
        phone_pattern = r'[\+\(]?[0-9][0-9 \-\(\)]{8,}[0-9]'
        phones = re.findall(phone_pattern, html_content)
        if phones:
            contact_info['phone'] = phones[0]
        
        return contact_info
