"""
Memory System for Sponsor Agent

This module implements a memory system using the Model Context Protocol (MCP)
for tracking processed URLs and company data.
"""

import os
import json
import asyncio
from typing import Dict, List, Optional, Any
from pydantic import BaseModel

import logfire
logger = logfire.getLogger("memory")

class MemoryClient:
    """Client for interacting with the MCP memory server"""
    
    def __init__(self, namespace: str = "sponsor_agent"):
        """Initialize the memory client"""
        self.namespace = namespace
        self.memory_file = f"{namespace}_memory.json"
        self._memory = self._load_memory()
    
    def _load_memory(self) -> Dict[str, Any]:
        """Load memory from file or initialize if not exists"""
        try:
            if os.path.exists(self.memory_file):
                with open(self.memory_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading memory: {e}")
        
        # Initialize empty memory structure
        return {
            "processed_urls": {},  # url -> {timestamp, suitable}
            "email_drafts": {},    # company_name -> {url, draft_id, timestamp}
            "metadata": {
                "total_processed": 0,
                "total_suitable": 0,
                "total_emails": 0
            }
        }
    
    def _save_memory(self) -> None:
        """Save memory to file"""
        try:
            with open(self.memory_file, 'w') as f:
                json.dump(self._memory, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving memory: {e}")
    
    async def has_processed_url(self, url: str) -> bool:
        """Check if URL has been processed"""
        return url in self._memory["processed_urls"]
    
    async def mark_url_processed(self, url: str, suitable: bool = False) -> None:
        """Mark URL as processed"""
        import time
        
        self._memory["processed_urls"][url] = {
            "timestamp": time.time(),
            "suitable": suitable
        }
        
        self._memory["metadata"]["total_processed"] += 1
        if suitable:
            self._memory["metadata"]["total_suitable"] += 1
        
        self._save_memory()
        logger.info(f"Marked URL as processed: {url} (suitable: {suitable})")
    
    async def store_email_draft(self, company_name: str, url: str, draft_id: str) -> None:
        """Store information about an email draft"""
        import time
        
        self._memory["email_drafts"][company_name] = {
            "url": url,
            "draft_id": draft_id,
            "timestamp": time.time()
        }
        
        self._memory["metadata"]["total_emails"] += 1
        self._save_memory()
        logger.info(f"Stored email draft for company: {company_name}")
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics"""
        return self._memory["metadata"]
    
    async def get_suitable_companies(self) -> List[str]:
        """Get list of suitable companies"""
        return [
            url for url, data in self._memory["processed_urls"].items()
            if data.get("suitable", False)
        ]
    
    async def get_email_drafts(self) -> Dict[str, Any]:
        """Get information about email drafts"""
        return self._memory["email_drafts"]
