import logfire
from typing import List, Dict, Tuple
from models import Product, Review, SearchResult, SearchCriteria

logger = logfire.getLogger(__name__)

class EvaluationAgent:
    def __init__(self):
        self.memory = {}

    def evaluate_products(self, products: List[Product], reviews: Dict[str, List[Review]], criteria: SearchCriteria) -> SearchResult:
        """Evaluate products based on their reviews and criteria."""
        logger.info(f"Evaluating {len(products)} products")
        
        scored_products = []
        for product in products:
            product_reviews = reviews.get(product.url, [])
            score = self._calculate_product_score(product, product_reviews, criteria)
            scored_products.append((product, score))
        
        # Sort by score in descending order
        scored_products.sort(key=lambda x: x[1], reverse=True)
        
        if not scored_products:
            return None
        
        best_product, best_score = scored_products[0]
        alternatives = [p for p, _ in scored_products[1:4]]  # Get next 3 best products
        
        return SearchResult(
            criteria=criteria,
            best_product=best_product,
            alternative_products=alternatives,
            reviews=reviews.get(best_product.url, []),
            confidence_score=best_score
        )

    def _calculate_product_score(self, product: Product, reviews: List[Review], criteria: SearchCriteria) -> float:
        """Calculate a score for a product based on its price, reviews, and criteria."""
        # Base score starts at 1.0
        score = 1.0
        
        # Price factor - products closer to budget get higher scores
        price_factor = self._calculate_price_factor(product.price, criteria.budget)
        score *= price_factor
        
        # Reviews factor
        if reviews:
            review_score = self._calculate_review_score(reviews)
            score *= review_score
        else:
            # Penalize products without reviews
            score *= 0.7
        
        return score

    def _calculate_price_factor(self, price: float, budget: float) -> float:
        """Calculate price factor. Products closer to budget get higher scores."""
        if price > budget:
            return 0.0  # Disqualify products over budget
        
        # Products at 80-100% of budget get highest scores
        price_ratio = price / budget
        if price_ratio >= 0.8:
            return 1.0
        else:
            # Lower scores for much cheaper products (might indicate lower quality)
            return 0.7 + (price_ratio * 0.3)

    def _calculate_review_score(self, reviews: List[Review]) -> float:
        """Calculate score based on reviews."""
        if not reviews:
            return 0.7  # Neutral score for no reviews
        
        total_score = 0.0
        weighted_count = 0
        
        for review in reviews:
            if review.rating is not None:
                weight = 1.0
                if review.text:  # Give more weight to reviews with text
                    weight = 1.2
                
                total_score += review.rating * weight
                weighted_count += weight
        
        if weighted_count == 0:
            return 0.7
        
        # Normalize to 0-1 range (assuming ratings are 0-5)
        return (total_score / weighted_count) / 5.0

    def store_in_memory(self, key: str, value: any):
        """Store data in memory."""
        self.memory[key] = value

    def get_from_memory(self, key: str) -> any:
        """Retrieve data from memory."""
        return self.memory.get(key)

    def clear_memory(self):
        """Clear the agent's memory."""
        self.memory.clear()