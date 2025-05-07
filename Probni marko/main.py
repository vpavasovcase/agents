import asyncio
import logfire
from typing import List, Dict
from models import SearchCriteria, Product, Review, SearchResult
from websearch_agent import WebSearchAgent
from webcrawl_agent import WebCrawlAgent
from evaluation_agent import EvaluationAgent

logger = logfire.getLogger(__name__)

class BestBuySystem:
    def __init__(self):
        self.websearch_agent = WebSearchAgent()
        self.webcrawl_agent = WebCrawlAgent()
        self.evaluation_agent = EvaluationAgent()

    async def initialize(self):
        """Initialize all agents."""
        await self.websearch_agent.initialize()
        await self.webcrawl_agent.initialize()

    async def cleanup(self):
        """Cleanup and close all agents."""
        await self.websearch_agent.close()
        await self.webcrawl_agent.close()
        self.clear_all_memory()

    def clear_all_memory(self):
        """Clear memory of all agents."""
        self.websearch_agent.clear_memory()
        self.webcrawl_agent.clear_memory()
        self.evaluation_agent.clear_memory()

    async def find_best_product(self, search_input: str) -> SearchResult:
        """Main workflow to find the best product based on user input."""
        # Parse user input into search criteria
        criteria = self._parse_user_input(search_input)
        logger.info(f"Starting search with criteria: {criteria}")

        try:
            # Step 1: Find relevant shops
            shops = await self.websearch_agent.search_shops(criteria)
            logger.info(f"Found {len(shops)} relevant shops")

            # Step 2: Crawl shops for products
            all_products = []
            for shop_url in shops:
                products = await self.webcrawl_agent.crawl_shop(shop_url, criteria.dict())
                all_products.extend(products)
            
            logger.info(f"Found {len(all_products)} products across all shops")

            # Step 3: Get reviews for each product
            all_reviews: Dict[str, List[Review]] = {}
            for product in all_products:
                review_urls = await self.websearch_agent.search_reviews(product.url)
                product_reviews = []
                for review_url in review_urls:
                    reviews = await self.webcrawl_agent.crawl_reviews(review_url, product.url)
                    product_reviews.extend(reviews)
                all_reviews[product.url] = product_reviews

            # Step 4: Evaluate products and find the best one
            result = self.evaluation_agent.evaluate_products(all_products, all_reviews, criteria)
            
            if result:
                logger.info(f"Found best product: {result.best_product.name}")
                return result
            else:
                logger.warning("No suitable products found")
                return None

        except Exception as e:
            logger.error(f"Error in find_best_product: {str(e)}")
            raise

    def _parse_user_input(self, input_text: str) -> SearchCriteria:
        """Parse user input text into structured search criteria."""
        # Simple parsing - in a real system this would use NLP
        budget = None
        location = None
        product_type = input_text

        # Extract budget
        if "imam" in input_text.lower() and "eur" in input_text.lower():
            parts = input_text.lower().split("imam")
            if len(parts) > 1:
                budget_part = parts[1].split("eur")[0].strip()
                try:
                    budget = float(budget_part)
                except:
                    pass

        # Extract location
        if "u hrvatskoj" in input_text.lower():
            location = "Hrvatska"

        return SearchCriteria(
            product_type=product_type,
            budget=budget if budget else 1000000,  # High default budget if none specified
            location=location,
            currency="EUR"
        )

async def main():
    """Main entry point of the application."""
    system = BestBuySystem()
    await system.initialize()

    try:
        while True:
            print("\nŠto želite kupiti? (upišite 'exit' za izlaz)")
            user_input = input("> ")
            
            if user_input.lower() == 'exit':
                break

            result = await system.find_best_product(user_input)
            
            if result:
                print("\nNajbolja opcija:")
                print(f"Naziv: {result.best_product.name}")
                print(f"Cijena: {result.best_product.price} {result.best_product.currency}")
                print(f"Link: {result.best_product.url}")
                
                if result.alternative_products:
                    print("\nAlternative:")
                    for alt in result.alternative_products:
                        print(f"- {alt.name} ({alt.price} {alt.currency}): {alt.url}")
            else:
                print("\nNažalost, nisam pronašao odgovarajući proizvod.")

    finally:
        await system.cleanup()

if __name__ == "__main__":
    logfire.init()
    asyncio.run(main())