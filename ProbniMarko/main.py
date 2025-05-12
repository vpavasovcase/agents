import asyncio
import logging
from typing import List, Dict, Optional
from models import SearchCriteria, Product, Review, SearchResult
from websearch_agent import WebSearchAgent
from webcrawl_agent import WebCrawlAgent
from evaluation_agent import EvaluationAgent
import os
from dotenv import load_dotenv
import json
import time

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('search_system.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def log_to_file(level: str, message: str, **kwargs):
    """Log to file with additional context."""
    log_entry = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'level': level,
        'message': message,
        **kwargs
    }
    
    with open('detailed_logs.jsonl', 'a', encoding='utf-8') as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
    
    if level == 'ERROR':
        logger.error(message)
    else:
        logger.info(message)

class BestBuySystem:
    def __init__(self):
        self.websearch_agent = WebSearchAgent()
        self.webcrawl_agent = WebCrawlAgent()
        self.evaluation_agent = EvaluationAgent()
        log_to_file('INFO', 'system_initialized', 
                    agents=["websearch", "webcrawl", "evaluation"])

    async def initialize(self):
        """Initialize all agents."""
        try:
            await self.websearch_agent.initialize()
            await self.webcrawl_agent.initialize()
            log_to_file('INFO', 'agents_initialized')
        except Exception as e:
            log_to_file('ERROR', 'initialization_failed', error=str(e))
            raise

    async def cleanup(self):
        """Cleanup and close all agents."""
        await self.websearch_agent.close()
        await self.webcrawl_agent.close()
        self.clear_all_memory()
        log_to_file('INFO', 'system_cleanup_complete')

    def clear_all_memory(self):
        """Clear memory of all agents."""
        self.websearch_agent.clear_memory()
        self.webcrawl_agent.clear_memory()
        self.evaluation_agent.clear_memory()
        log_to_file('INFO', 'memory_cleared')

    async def find_best_product(self, search_input: str) -> SearchResult:
        """Main workflow to find the best product based on user input."""
        try:
            # Create search criteria using OpenAI
            log_to_file('INFO', 'analyzing_search_input', 
                       input=search_input[:100])
            
            criteria = await SearchCriteria.from_text(search_input)
            log_to_file('INFO', 'search_criteria_created', 
                       num_requirements=len(criteria.requirements),
                       budget=criteria.budget)
            
            # Step 1: Search for products
            product_urls = await self.websearch_agent.search_shops(criteria)
            log_to_file('INFO', 'product_search_complete', 
                       num_products=len(product_urls))

            if not product_urls:
                log_to_file('WARNING', 'no_products_found',
                          criteria=str(criteria.dict()))
                raise ValueError("No products found matching your criteria")

            # Step 2: Crawl product pages and reviews
            products: List[Optional[Product]] = []
            reviews: Dict[str, List[Review]] = {}
            
            # Create tasks for crawling
            product_tasks = []
            review_tasks = []
            
            for url in product_urls:
                product_tasks.append(self.webcrawl_agent.crawl_product(url))
                review_tasks.append(self.webcrawl_agent.crawl_reviews(url))
            
            log_to_file('INFO', 'crawling_started', 
                       num_tasks=len(product_tasks))
            
            # Run tasks concurrently
            products = await asyncio.gather(*product_tasks)
            all_reviews = await asyncio.gather(*review_tasks)
            
            # Filter out None products and organize reviews
            valid_products = [p for p in products if p is not None]
            for url, review_list in zip(product_urls, all_reviews):
                if review_list:
                    reviews[url] = review_list

            log_to_file('INFO', 'crawling_complete', 
                       valid_products=len(valid_products),
                       total_reviews=sum(len(r) for r in reviews.values()))

            if not valid_products:
                log_to_file('WARNING', 'no_valid_products_found')
                raise ValueError("No valid products found matching your criteria")

            # Step 3: Evaluate products
            result = self.evaluation_agent.evaluate_products(valid_products, reviews, criteria)
            log_to_file('INFO', 'evaluation_complete', 
                       best_product_score=result.confidence_score,
                       num_alternatives=len(result.alternative_products))

            # Save results for debugging
            try:
                with open('last_search_result.json', 'w', encoding='utf-8') as f:
                    json.dump({
                        'query': search_input,
                        'requirements': [req.dict() for req in criteria.requirements],
                        'best_product': result.best_product.dict() if result.best_product else None,
                        'confidence_score': result.confidence_score,
                        'matching_specs': result.matching_specs,
                        'missing_specs': result.missing_specs
                    }, f, indent=2, ensure_ascii=False)
                log_to_file('INFO', 'results_saved_to_file')
            except Exception as e:
                log_to_file('ERROR', 'failed_to_save_results', error=str(e))

            return result

        except Exception as e:
            log_to_file('ERROR', 'search_error', error=str(e))
            raise

def print_product_details(product: Product) -> None:
    """Print formatted product details."""
    print(f"\nIme proizvoda: {product.name}")
    print(f"Cijena: {product.price} {product.currency}")
    print(f"Trgovina: {product.shop_url}")
    print(f"Link: {product.url}")
    
    if product.specifications:
        print("\nSpecifikacije:")
        for key, value in product.specifications.items():
            print(f"- {key}: {value}")

async def main():
    """Main entry point for testing."""
    system = BestBuySystem()
    await system.initialize()
    
    try:
        # Test search
        search_input = input("Unesite što tražite: ")
        result = await system.find_best_product(search_input)
        
        # Print results
        if result.best_product:
            print("\nNajbolji pronađeni proizvod:")
            print_product_details(result.best_product)
            print(f"\nOcjena podudaranja: {result.confidence_score:.2f}")
            
            if result.matching_specs:
                print("\nPodudarne specifikacije:")
                for spec in result.matching_specs:
                    print(f"✓ {spec}")
                    
            if result.missing_specs:
                print("\nNepodudarne specifikacije:")
                for spec in result.missing_specs:
                    print(f"✗ {spec}")
                    
            if result.alternative_products:
                print("\nAlternativni proizvodi:")
                for product in result.alternative_products:
                    print_product_details(product)
                    print("-" * 50)
        else:
            print("\nNažalost, nisu pronađeni odgovarajući proizvodi.")
            
    except Exception as e:
        log_to_file('ERROR', 'main_error', error=str(e))
        print(f"Greška: {str(e)}")
        
    finally:
        await system.cleanup()

if __name__ == "__main__":
    asyncio.run(main())