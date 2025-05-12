import asyncio
import random
import time
from typing import List, Dict, Any, Optional, Tuple
import logfire
import logging
from models import SearchCriteria, Product
import aiohttp
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
import re
import json
from tenacity import retry, stop_after_attempt, wait_exponential
from urllib.parse import urlparse
import time
from urllib.parse import urlparse

# Configure logfire
logfire.configure(
    environment="development",
    service_name="product-search"
)

logger = logging.getLogger(__name__)

def log_to_file(level: str, message: str, **kwargs):
    """Log to file with additional context."""
    log_entry = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'level': level,
        'message': message,
        'component': 'websearch_agent',
        **kwargs
    }
    
    with open('detailed_logs.jsonl', 'a', encoding='utf-8') as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
    
    if level == 'ERROR':
        logger.error(message)
    else:
        logger.info(message)

class WebSearchAgent:
    ECOMMERCE_SITES = [
        # Croatian sites
        'nabava.net',
        'jeftinije.hr',
        'links.hr',
        'hgspot.hr',
        'instar-informatika.hr',
        'protis.hr',
        'sancta-domenica.hr',
        'elipso.hr',
        'emmezeta.hr',
        'mikronis.hr',
    ]
    
    def __init__(self):
        self.session = None
        self.memory = {}
        self.ddgs = DDGS()
        self.last_search_time = 0
        logger.info('websearch_agent_initialized')

    async def initialize(self):
        """Initialize the web search agent."""
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)
            logger.info('aiohttp_session_initialized')

    async def close(self):
        """Close the web search agent."""
        if self.session:
            await self.session.close()
            self.session = None
            logger.info('aiohttp_session_closed')

    def clear_memory(self):
        """Clear search cache."""
        self.memory.clear()
        logger.info('memory_cleared')

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def _make_search_request(self, query: str) -> List[Dict[str, str]]:
        """Make a DuckDuckGo search request with retry logic."""
        current_time = time.time()
        if current_time - self.last_search_time < 1:  # Rate limit to 1 request per second
            await asyncio.sleep(1)
        
        try:
            results = list(self.ddgs.text(
                query,
                region='hr-HR',
                safesearch='off',
                max_results=10
            ))
            self.last_search_time = time.time()
            return results
        except Exception as e:
            logger.error(f"Search request failed: {str(e)}")
            if "429" in str(e):
                await asyncio.sleep(random.uniform(5, 10))
            raise

    async def search_shops(self, criteria: SearchCriteria) -> List[str]:
        """Search for shops that sell products matching the criteria."""
        logger.info(f"Searching for shops matching: {criteria.query}")
        
        query = f"{criteria.query} cijena price site:.hr"
        shops = []
        
        results = []
        try:
            results = await self._make_search_request(query)
        except Exception as e:
            logger.error(f"Shop search failed: {str(e)}")
            return [f"https://www.{site}" for site in self.ECOMMERCE_SITES[:3]]  # Return top 3 default shops on error
            
        for result in results:
            url = result.get('link', '')
            domain = urlparse(url).netloc
            
            if any(site in domain for site in self.ECOMMERCE_SITES):
                base_url = f"https://{domain}"
                if base_url not in shops:
                    shops.append(base_url)
                    if len(shops) >= 5:  # Limit to top 5 shops
                        break
        
        logger.info(f"Found {len(shops)} relevant shops")
        return shops if shops else [f"https://www.{site}" for site in self.ECOMMERCE_SITES[:3]]

    async def search_reviews(self, product_url: str) -> List[str]:
        """Find review sources for a specific product."""
        logger.info(f"Searching reviews for product: {product_url}")
        
        domain = urlparse(product_url).netloc
        product_name = product_url.split('/')[-1].replace('-', ' ')
        
        review_queries = [
            f"{product_name} review recenzija site:.hr",
            f"{product_name} iskustva forum site:.hr",
            f"site:{domain} {product_name} review"
        ]
            
            review_urls = set()
            for query in review_queries:
                await asyncio.sleep(2)  # Rate limiting between queries
                try:
                    results = await self._make_search_request(query)
                    for result in results:
                        url = result.get('link', '')
                        if 'forum' in url or 'review' in url or 'recenzija' in url:
                            review_urls.add(url)
                except Exception as e:
                    logger.error(f"Review search failed for query '{query}': {str(e)}")
                    continue
            
            logger.info(f"Found {len(review_urls)} review sources")
            return list(review_urls)[:5]  # Return top 5 review sources
            
        except Exception as e:
            logger.error(f"Review search failed: {str(e)}")
            return [f"{product_url}#reviews"]  # Fallback to product page reviews

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def get_similar_products(self, product_url: str) -> List[str]:
        """Find similar products."""
        try:
            domain = urlparse(product_url).netloc
            product_name = product_url.split('/')[-1].replace('-', ' ')
            
            query = f"site:{domain} {product_name} slično"
            results = await self._make_search_request(query)
            
            similar_urls = []
            seen_paths = set()
            
            for result in results:
                url = result.get('link', '')
                path = urlparse(url).path
                
                if url != product_url and path not in seen_paths:
                    similar_urls.append(url)
                    seen_paths.add(path)
            
            logger.info(f"Found {len(similar_urls)} similar products")
            return similar_urls[:3]  # Return top 3 similar products
            
        except Exception as e:
            logger.error(f"Similar products search failed: {str(e)}")
            return []

    async def run_sync(self, urls: List[str], callback) -> None:
        """Run synchronous processing of URLs."""
        for url in urls:
            try:
                await callback(url)
            except Exception as e:
                logger.error(f"Error processing URL {url}: {str(e)}")
                continue
