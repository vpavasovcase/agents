import asyncio
from typing import List, Dict
import logfire
from models import Product, Review
import aiohttp
from bs4 import BeautifulSoup
from firecrawl import FireCrawl

logger = logfire.getLogger(__name__)

class WebCrawlAgent:
    def __init__(self):
        self.session = None
        self.memory = {}
        self.crawler = FireCrawl()

    async def initialize(self):
        if not self.session:
            self.session = aiohttp.ClientSession()

    async def close(self):
        if self.session:
            await self.session.close()
            self.session = None

    async def crawl_shop(self, shop_url: str, criteria: dict) -> List[Product]:
        """Crawl a shop website for products matching criteria."""
        logger.info(f"Crawling shop: {shop_url}")
        
        try:
            # Use FireCrawl to extract product information
            # In a real implementation, you would configure proper selectors and rules
            products = []
            async with self.session.get(shop_url) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Example product extraction - would need to be customized per shop
                    product_elements = soup.find_all('div', class_='product')
                    for elem in product_elements:
                        if self._matches_criteria(elem, criteria):
                            product = self._extract_product(elem, shop_url)
                            if product:
                                products.append(product)
            
            return products
        except Exception as e:
            logger.error(f"Error crawling {shop_url}: {str(e)}")
            return []

    async def crawl_reviews(self, review_url: str, product_url: str) -> List[Review]:
        """Crawl reviews for a specific product."""
        logger.info(f"Crawling reviews from: {review_url}")
        
        try:
            reviews = []
            async with self.session.get(review_url) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Example review extraction - would need to be customized per site
                    review_elements = soup.find_all('div', class_='review')
                    for elem in review_elements:
                        review = self._extract_review(elem, product_url, review_url)
                        if review:
                            reviews.append(review)
            
            return reviews
        except Exception as e:
            logger.error(f"Error crawling reviews {review_url}: {str(e)}")
            return []

    def _matches_criteria(self, product_element: BeautifulSoup, criteria: dict) -> bool:
        """Check if a product matches the search criteria."""
        try:
            price_elem = product_element.find('span', class_='price')
            if price_elem:
                price = float(price_elem.text.strip().replace('€', ''))
                return price <= criteria.get('budget', float('inf'))
            return False
        except:
            return False

    def _extract_product(self, product_element: BeautifulSoup, shop_url: str) -> Product:
        """Extract product information from HTML element."""
        try:
            name = product_element.find('h2').text.strip()
            price_text = product_element.find('span', class_='price').text.strip()
            price = float(price_text.replace('€', ''))
            url = product_element.find('a')['href']
            
            return Product(
                name=name,
                price=price,
                currency='EUR',
                url=url,
                shop_url=shop_url,
                description=product_element.find('div', class_='description').text.strip()
            )
        except Exception as e:
            logger.error(f"Error extracting product: {str(e)}")
            return None

    def _extract_review(self, review_element: BeautifulSoup, product_url: str, source: str) -> Review:
        """Extract review information from HTML element."""
        try:
            text = review_element.find('div', class_='review-text').text.strip()
            rating = float(review_element.find('span', class_='rating').text.strip())
            date = review_element.find('span', class_='date').text.strip()
            
            return Review(
                product_url=product_url,
                text=text,
                rating=rating,
                source=source,
                date=date
            )
        except Exception as e:
            logger.error(f"Error extracting review: {str(e)}")
            return None

    def store_in_memory(self, key: str, value: any):
        """Store data in memory."""
        self.memory[key] = value

    def get_from_memory(self, key: str) -> any:
        """Retrieve data from memory."""
        return self.memory.get(key)

    def clear_memory(self):
        """Clear the agent's memory."""
        self.memory.clear()