import asyncio
from typing import List, Dict, Any, Optional, Tuple, Union, Sequence
import logging
from models import Product, Review
import aiohttp
from bs4 import BeautifulSoup, Tag
from bs4.element import NavigableString, ResultSet
import re
import urllib.parse
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('search_system.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class WebCrawlAgent:
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.memory: Dict[str, Any] = {}
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'hr-HR,hr;q=0.9,en-US;q=0.8,en;q=0.7',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }

    async def initialize(self) -> None:
        if not self.session:
            self.session = aiohttp.ClientSession(headers=self.headers)

    async def close(self) -> None:
        if self.session:
            await self.session.close()
            self.session = None

    def clear_memory(self) -> None:
        self.memory.clear()

    def store_in_memory(self, key: str, value: Any) -> None:
        """Store value in memory."""
        self.memory[key] = value

    def get_from_memory(self, key: str) -> Any:
        """Get value from memory."""
        return self.memory.get(key)

    async def fetch_page(self, url: str) -> Optional[str]:
        """Fetch a page and return its HTML content."""
        if not self.session:
            await self.initialize()
            
        try:
            if not self.session:
                raise RuntimeError("Failed to initialize session")
            
            timeout = aiohttp.ClientTimeout(total=30)
            async with self.session.get(url, timeout=timeout) as response:
                if response.status == 200:
                    return await response.text()
                else:
                    logger.error(f"Failed to fetch {url}: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {str(e)}")
            return None

    def find_all_safe(self, element: Optional[Tag], name: Optional[Union[str, List[str]]] = None, **kwargs) -> Sequence[Tag]:
        """Safely call find_all on a BeautifulSoup element."""
        if element and isinstance(element, Tag):
            results = element.find_all(name, **kwargs)
            return [r for r in results if isinstance(r, Tag)]
        return []

    def find_safe(self, element: Optional[Tag], name: Optional[str] = None, **kwargs) -> Optional[Tag]:
        """Safely call find on a BeautifulSoup element."""
        if element and isinstance(element, Tag):
            result = element.find(name, **kwargs)
            if isinstance(result, Tag):
                return result
        return None

    def _extract_price(self, text: str) -> Tuple[Optional[float], str]:
        """Extract price and currency from text."""
        # Common price patterns
        patterns = [
            # Croatian format (HRK)
            (r'(\d+(?:\.\d{3})*(?:,\d{2})?)\s*(?:kn|hrk|kuna)', 'HRK'),
            # Euro format
            (r'(\d+(?:\.\d{3})*(?:,\d{2})?)\s*(?:€|eur)', 'EUR'),
            # Generic number
            (r'(\d+(?:\.\d{3})*(?:,\d{2})?)', 'HRK')  # Default to HRK
        ]
        
        for pattern, currency in patterns:
            match = re.search(pattern, text.lower())
            if match:
                price_str = match.group(1).replace('.', '').replace(',', '.')
                try:
                    return float(price_str), currency
                except ValueError:
                    continue
        return None, 'HRK'

    async def crawl_product(self, url: str) -> Optional[Product]:
        """Crawl a product page for information."""
        logger.info(f"Crawling product: {url}")
        
        html = await self.fetch_page(url)
        if not html:
            return None
            
        soup = BeautifulSoup(html, 'html.parser')
        
        try:
            # Try common patterns for product name
            name_elem = self.find_safe(soup, 'h1') or \
                       self.find_safe(soup, class_=re.compile(r'product[-_]?title|title|name', re.I)) or \
                       self.find_safe(soup, 'title')
            
            name = name_elem.get_text().strip() if name_elem else "Unknown Product"
            
            # Try to find price
            price_elem = self.find_safe(soup, class_=re.compile(r'price|cijena', re.I))
            price_text = price_elem.get_text().strip() if price_elem else ""
            price, currency = self._extract_price(price_text)
            
            if not price:
                logger.warning(f"Could not extract price from {url}")
                return None
            
            # Get description
            desc_elem = self.find_safe(soup, class_=re.compile(r'description|opis', re.I))
            description = desc_elem.get_text().strip() if desc_elem else ""
            
            # Extract specifications
            specs: Dict[str, str] = {}
            spec_table = self.find_safe(soup, 'table', class_=re.compile(r'spec|attribute|karakteristik', re.I))
            
            if spec_table:
                rows = self.find_all_safe(spec_table, 'tr')
                for row in rows:
                    cells = self.find_all_safe(row, ['th', 'td'])
                    if len(cells) >= 2:
                        key = cells[0].get_text().strip()
                        value = cells[1].get_text().strip()
                        if key and value:
                            specs[key] = value
            
            # Create product
            product = Product(
                name=name,
                price=price,
                currency=currency,
                url=url,
                shop_url=urllib.parse.urlparse(url).netloc,
                description=description,
                specifications=specs
            )
            
            # Store in memory
            self.store_in_memory(f"product_{url}", product)
            logger.info(f"Successfully crawled product: {name}")
            
            return product
            
        except Exception as e:
            logger.error(f"Error parsing product {url}: {str(e)}")
            return None

    async def crawl_reviews(self, url: str) -> List[Review]:
        """Crawl reviews for a product."""
        logger.info(f"Crawling reviews for: {url}")
        
        reviews: List[Review] = []
        
        try:
            html = await self.fetch_page(url)
            if not html:
                return reviews
                
            soup = BeautifulSoup(html, 'html.parser')
            
            # Find review section
            review_section = self.find_safe(soup, class_=re.compile(r'review|rating|ocjen', re.I))
            if not review_section:
                return reviews
                
            # Extract reviews
            review_elements = self.find_all_safe(review_section, class_=re.compile(r'review|comment|komentar', re.I))
            
            for elem in review_elements:
                try:
                    # Get review text
                    text_elem = self.find_safe(elem, class_=re.compile(r'text|content|description', re.I))
                    text = text_elem.get_text().strip() if text_elem else ""
                    
                    if not text:
                        continue
                    
                    # Try to get rating
                    rating_elem = self.find_safe(elem, class_=re.compile(r'rating|score|stars|ocjena', re.I))
                    rating = None
                    if rating_elem:
                        rating_text = rating_elem.get_text().strip()
                        try:
                            # Convert X/5 or X/10 to float
                            if '/' in rating_text:
                                num, den = map(float, rating_text.split('/'))
                                rating = (num / den) * 5
                            else:
                                rating = float(rating_text)
                        except ValueError:
                            pass
                    
                    # Get date if available
                    date_elem = self.find_safe(elem, class_=re.compile(r'date|time|datum', re.I))
                    date = date_elem.get_text().strip() if date_elem else None
                    
                    review = Review(
                        product_url=url,
                        text=text,
                        rating=rating,
                        source=urllib.parse.urlparse(url).netloc,
                        date=date
                    )
                    
                    reviews.append(review)
                    
                except Exception as e:
                    logger.error(f"Error parsing review: {str(e)}")
                    continue
            
            # Store in memory
            self.store_in_memory(f"reviews_{url}", reviews)
            logger.info(f"Found {len(reviews)} reviews for {url}")
            
            return reviews
            
        except Exception as e:
            logger.error(f"Error crawling reviews for {url}: {str(e)}")
            return reviews