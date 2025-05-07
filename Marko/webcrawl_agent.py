import os
import asyncio
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
import logfire
from openai import OpenAI
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from playwright.async_api import async_playwright
from memory_client import MemoryClient, Entity, Relation

# Initialize logfire
logfire.configure()
logger = logfire.getLogger(__name__)

# Setup OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Define Pydantic models for structured data
class ProductFeature(BaseModel):
    name: str
    value: str

class Product(BaseModel):
    id: str  # Unique identifier for the product
    name: str
    brand: Optional[str] = None
    model: Optional[str] = None
    price: float
    currency: str = "EUR"
    url: str
    image_url: Optional[str] = None
    webshop_name: str
    features: List[ProductFeature] = []
    description: Optional[str] = None
    in_stock: Optional[bool] = True

class ProductReview(BaseModel):
    id: str  # Unique identifier for the review
    product_id: str
    source: str
    author: Optional[str] = None
    rating: Optional[float] = Field(None, ge=0, le=5)
    content: str
    pros: List[str] = []
    cons: List[str] = []
    date: Optional[str] = None
    url: str

class WebcrawlAgent:
    def __init__(self):
        # Initialize LLM
        self.llm = ChatOpenAI(temperature=0, model="gpt-4o")
        
        # Initialize memory client
        self.memory_client = MemoryClient()
        
        logger.info("WebcrawlAgent initialized")

    async def crawl_webshop(self, webshop_info: Dict, product_query: str, budget: float, requirements: List[str]) -> List[Product]:
        """Crawl a webshop and extract product information that matches the query and budget."""
        logger.info(f"Crawling webshop: {webshop_info['name']} ({webshop_info['url']}) for {product_query}")
        
        try:
            # Use Playwright to visit the website and extract content
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                # Navigate to the URL
                await page.goto(webshop_info['url'], wait_until="networkidle")
                
                # Get the page content
                content = await page.content()
                
                # In a real scenario, we'd navigate and click through the site
                # For this example, we'll just extract what we can from the landing page
                
                # If the URL isn't a product category page, try to search for the product
                if product_query.lower() not in content.lower():
                    logger.info(f"Product not found on landing page, trying to search")
                    
                    # Look for a search input
                    search_input = await page.query_selector('input[type="search"], input[placeholder*="search"], input[placeholder*="Search"], input[name="q"]')
                    
                    if search_input:
                        await search_input.fill(product_query)
                        await search_input.press("Enter")
                        await page.wait_for_load_state("networkidle")
                        content = await page.content()
                
                # Extract product listings from the page
                products = await self._extract_products_from_page(page, content, product_query, budget, webshop_info['name'], requirements)
                
                # Close the browser
                await browser.close()
                
                # Store products in memory
                for product in products:
                    product_entity = Entity(
                        type="product",
                        id=product.id,
                        properties={
                            "name": product.name,
                            "brand": product.brand or "",
                            "model": product.model or "",
                            "price": product.price,
                            "currency": product.currency,
                            "url": product.url,
                            "image_url": product.image_url or "",
                            "webshop_name": product.webshop_name,
                            "description": product.description or "",
                            "in_stock": product.in_stock
                        }
                    )
                    await self.memory_client.upsert_entity(product_entity)
                    
                    # Add features as separate entities with relations to the product
                    for feature in product.features:
                        feature_id = f"{product.id}_feature_{feature.name}".replace(" ", "_").lower()
                        feature_entity = Entity(
                            type="product_feature",
                            id=feature_id,
                            properties={
                                "name": feature.name,
                                "value": feature.value
                            }
                        )
                        await self.memory_client.upsert_entity(feature_entity)
                        
                        # Create relation between product and feature
                        relation = Relation(
                            source_id=product.id,
                            target_id=feature_id,
                            type="has_feature"
                        )
                        await self.memory_client.upsert_relation(relation)
                    
                    # Create relation between webshop and product
                    relation = Relation(
                        source_id=webshop_info['url'],
                        target_id=product.id,
                        type="sells_product"
                    )
                    await self.memory_client.upsert_relation(relation)
                
                logger.info(f"Found {len(products)} products at {webshop_info['name']}")
                return products
                
        except Exception as e:
            logger.error(f"Error crawling webshop {webshop_info['name']}: {e}")
            return []

    async def _extract_products_from_page(self, page, content: str, product_query: str, budget: float, webshop_name: str, requirements: List[str]) -> List[Product]:
        """Extract product information from a webpage using LLM."""
        prompt = ChatPromptTemplate.from_template(
            """
            Act as a web scraping expert who is extracting product information from an HTML page.
            
            The user is looking for: {product_query}
            Budget: {budget} {currency}
            Requirements: {requirements}
            Webshop name: {webshop_name}
            Current URL: {current_url}
            
            Analyze this HTML content and extract products that:
            1. Match the product query
            2. Are within the budget
            3. Meet as many of the requirements as possible
            
            HTML content (partial):
            {content_sample}
            
            Return a JSON list of products with the following structure:
            [
                {{
                    "id": "unique_id_for_product",
                    "name": "Product full name",
                    "brand": "Brand name if available",
                    "model": "Model number if available",
                    "price": 99.99,
                    "currency": "EUR",
                    "url": "Full URL to the product page",
                    "image_url": "URL to product image if available",
                    "webshop_name": "{webshop_name}",
                    "features": [
                        {{ "name": "Feature name", "value": "Feature value" }},
                        {{ "name": "Another feature", "value": "Feature value" }}
                    ],
                    "description": "Brief product description",
                    "in_stock": true
                }},
                ...
            ]
            
            Only include products that are clearly matching the query and are within the budget.
            If you cannot find specific information, use null for that field.
            """
        )
        
        # Limit content sample to avoid token limits
        content_sample = content[:50000]
        
        chain = prompt | self.llm | StrOutputParser()
        
        products_json = await chain.ainvoke({
            "product_query": product_query,
            "budget": budget,
            "currency": "EUR",
            "requirements": requirements,
            "webshop_name": webshop_name,
            "current_url": page.url,
            "content_sample": content_sample
        })
        
        # Parse results to structured format
        try:
            from json import loads
            products_data = loads(products_json)
            products = [Product(**product) for product in products_data]
            return products
        except Exception as e:
            logger.error(f"Error parsing products: {e}")
            return []

    async def crawl_reviews(self, review_source: Dict, product: Dict) -> List[ProductReview]:
        """Crawl a review source and extract reviews for a specific product."""
        product_id = product["id"]
        product_name = product["name"]
        logger.info(f"Crawling reviews for {product_name} from {review_source['name']}")
        
        try:
            # Use Playwright to visit the review website
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                # Navigate to the URL
                await page.goto(review_source['url'], wait_until="networkidle")
                
                # Get the page content
                content = await page.content()
                
                # Extract reviews from the page
                reviews = await self._extract_reviews_from_page(content, product, review_source['name'], review_source['url'])
                
                # Close the browser
                await browser.close()
                
                # Store reviews in memory
                for review in reviews:
                    review_entity = Entity(
                        type="product_review",
                        id=review.id,
                        properties={
                            "product_id": review.product_id,
                            "source": review.source,
                            "author": review.author or "Anonymous",
                            "rating": review.rating or 0.0,
                            "content": review.content,
                            "pros": review.pros,
                            "cons": review.cons,
                            "date": review.date or "Unknown",
                            "url": review.url
                        }
                    )
                    await self.memory_client.upsert_entity(review_entity)
                    
                    # Create relation between product and review
                    relation = Relation(
                        source_id=product_id,
                        target_id=review.id,
                        type="has_review"
                    )
                    await self.memory_client.upsert_relation(relation)
                
                logger.info(f"Found {len(reviews)} reviews for {product_name} from {review_source['name']}")
                return reviews
                
        except Exception as e:
            logger.error(f"Error crawling reviews from {review_source['name']}: {e}")
            return []

    async def _extract_reviews_from_page(self, content: str, product: Dict, source_name: str, source_url: str) -> List[ProductReview]:
        """Extract product reviews from a webpage using LLM."""
        prompt = ChatPromptTemplate.from_template(
            """
            Act as a web scraping expert who is extracting product reviews from an HTML page.
            
            Product information:
            - Name: {product_name}
            - Brand: {product_brand}
            - Model: {product_model}
            
            Review source: {source_name}
            URL: {source_url}
            
            Analyze this HTML content and extract reviews that seem to be for this product or very similar products.
            
            HTML content (partial):
            {content_sample}
            
            Return a JSON list of reviews with the following structure:
            [
                {{
                    "id": "unique_id_for_review",
                    "product_id": "{product_id}",
                    "source": "{source_name}",
                    "author": "Reviewer name if available",
                    "rating": 4.5,
                    "content": "The full review text",
                    "pros": ["Pro point 1", "Pro point 2"],
                    "cons": ["Con point 1", "Con point 2"],
                    "date": "Review date if available",
                    "url": "{source_url}"
                }},
                ...
            ]
            
            If you cannot find specific information, use null for that field.
            If no rating is explicitly given but sentiment is positive, estimate a rating between 3-5.
            If sentiment is negative, estimate a rating between 1-3.
            """
        )
        
        # Limit content sample to avoid token limits
        content_sample = content[:50000]
        
        chain = prompt | self.llm | StrOutputParser()
        
        reviews_json = await chain.ainvoke({
            "product_id": product["id"],
            "product_name": product["name"],
            "product_brand": product.get("brand", ""),
            "product_model": product.get("model", ""),
            "source_name": source_name,
            "source_url": source_url,
            "content_sample": content_sample
        })
        
        # Parse results to structured format
        try:
            from json import loads
            reviews_data = loads(reviews_json)
            reviews = [ProductReview(**review) for review in reviews_data]
            return reviews
        except Exception as e:
            logger.error(f"Error parsing reviews: {e}")
            return []

if __name__ == "__main__":
    # For testing purposes
    agent = WebcrawlAgent()
    
    async def test_crawl():
        webshop = {
            "name": "Links",
            "url": "https://www.links.hr/hr/slusalice",
            "description": "Croatian electronics retailer"
        }
        
        products = await agent.crawl_webshop(
            webshop, 
            "bluetooth slušalice android", 
            100.0, 
            ["wireless", "microphone", "good battery life"]
        )
        
        if products:
            review_source = {
                "name": "Links Reviews",
                "url": "https://www.links.hr/hr/slusalice"  # In reality this would be a review page
            }
            
            reviews = await agent.crawl_reviews(review_source, products[0].dict())
    
    # Run the test
    asyncio.run(test_crawl())
