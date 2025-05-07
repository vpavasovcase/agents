import asyncio
import os
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
import logfire
from langchain_community.utilities import GoogleSearchAPIWrapper
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from openai import OpenAI
import nest_asyncio
from memory_client import MemoryClient, Entity, Relation

# Initialize logfire
logfire.configure()
logger = logfire.getLogger(__name__)

# Setup OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Define Pydantic models for structured outputs
class WebshopInfo(BaseModel):
    name: str
    url: str
    description: Optional[str] = None
    relevance_score: Optional[float] = Field(None, ge=0, le=1)

class ProductReviewSource(BaseModel):
    name: str
    url: str
    description: Optional[str] = None

class SearchResults(BaseModel):
    webshops: List[WebshopInfo]
    review_sources: List[ProductReviewSource]

class WebsearchAgent:
    def __init__(self):
        # Initialize Google Search
        self.search = GoogleSearchAPIWrapper(
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            google_cse_id=os.getenv("GOOGLE_CSE_ID"),
        )
        
        # Initialize LLM
        self.llm = ChatOpenAI(temperature=0, model="gpt-4o")
        
        # Initialize memory client
        self.memory_client = MemoryClient()
        
        # Apply nest_asyncio to handle asyncio in Jupyter/interactive environments
        nest_asyncio.apply()
        
        logger.info("WebsearchAgent initialized")

    async def search_webshops(self, product_description: str, budget: float, location: str = "Hrvatska") -> List[WebshopInfo]:
        """Search for webshops that sell the specified product in the given location."""
        logger.info(f"Searching for webshops for: {product_description} with budget {budget} in {location}")
        
        # Craft search query
        search_query = f"best {product_description} webshop {location} price under {budget}"
        
        # Get search results
        search_results = self.search.results(search_query, num_results=10)
        
        # Process search results with LLM to extract webshop information
        prompt = ChatPromptTemplate.from_template(
            """
            Analyze these search results and identify webshops that sell {product_description} in {location}.
            Focus on online stores that likely have products within the budget of {budget}.
            
            Search results:
            {search_results}
            
            Return a JSON list of webshops with the following structure:
            [
                {
                    "name": "Webshop name",
                    "url": "Full URL to the webshop homepage or product category page",
                    "description": "Brief description of the webshop",
                    "relevance_score": 0.95 (a score between 0-1 indicating how relevant this webshop is)
                },
                ...
            ]
            Only include actual webshops where someone can buy products, not review sites or blogs.
            """
        )
        
        chain = prompt | self.llm | StrOutputParser()
        
        webshops_json = await chain.ainvoke({
            "product_description": product_description,
            "budget": budget,
            "location": location,
            "search_results": search_results
        })
        
        # Parse results to structured format
        try:
            from json import loads
            webshops_data = loads(webshops_json)
            webshops = [WebshopInfo(**webshop) for webshop in webshops_data]
            
            # Store webshops in memory
            for webshop in webshops:
                webshop_entity = Entity(
                    type="webshop",
                    id=webshop.url,
                    properties={
                        "name": webshop.name,
                        "url": webshop.url,
                        "description": webshop.description or "",
                        "relevance_score": webshop.relevance_score or 0.5
                    }
                )
                await self.memory_client.upsert_entity(webshop_entity)
            
            logger.info(f"Found {len(webshops)} webshops")
            return webshops
        except Exception as e:
            logger.error(f"Error parsing webshops: {e}")
            return []

    async def search_product_reviews(self, product_name: str, model: str) -> List[ProductReviewSource]:
        """Search for reviews of a specific product."""
        logger.info(f"Searching for reviews of: {product_name} {model}")
        
        # Craft search query
        search_query = f"{product_name} {model} review ratings"
        
        # Get search results
        search_results = self.search.results(search_query, num_results=5)
        
        # Process search results with LLM to extract review sources
        prompt = ChatPromptTemplate.from_template(
            """
            Analyze these search results and identify good sources of reviews for {product_name} {model}.
            
            Search results:
            {search_results}
            
            Return a JSON list of review sources with the following structure:
            [
                {
                    "name": "Review site name",
                    "url": "Full URL to the review page",
                    "description": "Brief description of what this review contains"
                },
                ...
            ]
            Focus on trustworthy review sites with detailed reviews, not just listings.
            """
        )
        
        chain = prompt | self.llm | StrOutputParser()
        
        reviews_json = await chain.ainvoke({
            "product_name": product_name,
            "model": model,
            "search_results": search_results
        })
        
        # Parse results to structured format
        try:
            from json import loads
            reviews_data = loads(reviews_json)
            review_sources = [ProductReviewSource(**review) for review in reviews_data]
            
            # Store review sources in memory with relation to product
            product_entity_id = f"{product_name}_{model}".replace(" ", "_").lower()
            
            for review_source in review_sources:
                review_entity = Entity(
                    type="review_source",
                    id=review_source.url,
                    properties={
                        "name": review_source.name,
                        "url": review_source.url,
                        "description": review_source.description or ""
                    }
                )
                await self.memory_client.upsert_entity(review_entity)
                
                # Create relation between product and review
                relation = Relation(
                    source_id=product_entity_id,
                    target_id=review_source.url,
                    type="has_review_source"
                )
                await self.memory_client.upsert_relation(relation)
            
            logger.info(f"Found {len(review_sources)} review sources for {product_name} {model}")
            return review_sources
        except Exception as e:
            logger.error(f"Error parsing review sources: {e}")
            return []

    def parse_user_input(self, user_input: str) -> Dict:
        """Extract product info, budget, and location from user input."""
        logger.info(f"Parsing user input: {user_input}")
        
        prompt = ChatPromptTemplate.from_template(
            """
            Extract the following information from the user input:
            1. What product they want to buy
            2. Their budget (in EUR or other currency)
            3. Their location (default to Croatia if not specified)
            4. Any specific requirements or features they want
            
            User input: {user_input}
            
            Return the information in this JSON format:
            {{
                "product_description": "detailed product description",
                "budget": 100.0,
                "currency": "EUR",
                "location": "Croatia",
                "requirements": ["requirement1", "requirement2"]
            }}
            """
        )
        
        chain = prompt | self.llm | StrOutputParser()
        
        try:
            result = asyncio.run(chain.ainvoke({"user_input": user_input}))
            from json import loads
            parsed_input = loads(result)
            logger.info(f"Parsed input: {parsed_input}")
            return parsed_input
        except Exception as e:
            logger.error(f"Error parsing user input: {e}")
            return {
                "product_description": user_input,
                "budget": 100.0,
                "currency": "EUR",
                "location": "Hrvatska",
                "requirements": []
            }

if __name__ == "__main__":
    # For testing purposes
    agent = WebsearchAgent()
    user_input = "Hoću kupiti best buy bluetooth slušalice za android u hrvatskoj, imam 100 EUR."
    parsed_input = agent.parse_user_input(user_input)
    
    async def test_search():
        webshops = await agent.search_webshops(
            parsed_input["product_description"], 
            parsed_input["budget"], 
            parsed_input["location"]
        )
        print(f"Found {len(webshops)} webshops")
        for shop in webshops:
            print(f"- {shop.name}: {shop.url}")
    
    asyncio.run(test_search())
