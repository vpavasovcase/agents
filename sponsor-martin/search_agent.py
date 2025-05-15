"""
Web Search Agent for Sponsor System

This agent searches the web for potential sponsor companies using DuckDuckGo.
"""

import os
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import aiohttp
import asyncio

from pydantic_ai.common_tools.duckduckgo import duckduckgo_search_tool

import logfire
logger = logfire.instrument("search_agent")

class SearchResult(BaseModel):
    """Structure for search results"""
    title: str
    url: str
    description: Optional[str] = None

class WebSearchAgent:
    """Agent for searching the web for potential sponsors"""
    
    def __init__(self, memory_client):
        """Initialize the search agent"""
        self.memory_client = memory_client
        self.system_prompt = """
        You are a specialized search agent that finds companies that might be interested 
        in sponsoring specific events. Focus on finding relevant businesses based on the search query.
        
        For example, if organizing a cycling race in Osijek, focus on finding bicycle shops, 
        sports equipment stores, local businesses, and other potential sponsors in that area.
        
        Return only business websites, not news articles, forums, or irrelevant pages.
        Prioritize company websites with contact information.
        """
    
    async def search(self, query: str, num_results: int = 20) -> List[str]:
        """
        Search for potential sponsor companies
        
        Args:
            query: Search query to find relevant companies
            num_results: Number of results to return
            
        Returns:
            List of URLs to potential sponsor company websites
        """
        logger.info(f"Searching for: {query}")
        
        try:
            # Use DuckDuckGo search tool from Pydantic AI
            search_results = await duckduckgo_search_tool.query(
                query=query,
                num_results=num_results,
                system_prompt=self.system_prompt
            )
            
            # Extract URLs
            urls = []
            for result in search_results.results:
                # Check if URL is already processed
                if not await self.memory_client.has_processed_url(result.url):
                    urls.append(result.url)
                    logger.info(f"Found new potential sponsor: {result.title} ({result.url})")
                else:
                    logger.info(f"Skipping already processed URL: {result.url}")
            
            return urls
            
        except Exception as e:
            logger.error(f"Error during search: {e}")
            return []
    
    async def filter_results(self, results: List[SearchResult]) -> List[str]:
        """
        Filter search results to include only relevant companies
        
        Args:
            results: List of search results
            
        Returns:
            Filtered list of URLs
        """
        filtered_urls = []
        
        for result in results:
            # Skip social media, news sites, etc.
            skip_domains = ["facebook.com", "twitter.com", "youtube.com", "news", "forum", 
                           "wikipedia.org", "instagram.com", "linkedin.com"]
            
            if any(domain in result.url.lower() for domain in skip_domains):
                continue
                
            # Check if already processed
            if await self.memory_client.has_processed_url(result.url):
                continue
                
            filtered_urls.append(result.url)
        
        return filtered_urls
