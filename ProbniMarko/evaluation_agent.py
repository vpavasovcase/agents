import logging
from typing import List, Dict, Tuple, Any, Optional
from models import Product, Review, SearchResult, SearchCriteria
import re
from deep_translator import GoogleTranslator

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EvaluationAgent:
    def __init__(self):
        self.memory: Dict[str, Any] = {}

    def clear_memory(self) -> None:
        """Clear the agent's memory."""
        self.memory.clear()

    def store_in_memory(self, key: str, value: Any) -> None:
        """Store data in memory."""
        self.memory[key] = value

    def get_from_memory(self, key: str) -> Any:
        """Retrieve data from memory."""
        return self.memory.get(key)

    def _normalize_text(self, text: str, target_lang: str) -> str:
        """Normalize text by translating if needed."""
        if not text:
            return ""
        
        translator = GoogleTranslator(source='auto', target=target_lang)
        try:
            return translator.translate(text)
        except:
            return text

    def _calculate_spec_match_score(self, product: Product, criteria: SearchCriteria) -> Tuple[float, List[str], List[str]]:
        """Calculate how well product matches required specifications and free-form text."""
        score = 0.0
        matched_specs = []
        missing_specs = []
        
        # Convert product specs and description to target language if needed
        target_lang = "en" if criteria.language not in ["hr", "en"] else criteria.language
        
        prod_specs = {
            k.lower(): self._normalize_text(v.lower(), target_lang)
            for k, v in product.specifications.items()
        }
        
        desc_norm = self._normalize_text(
            product.description.lower() if product.description else "",
            target_lang
        )
        
        # Match extracted specifications
        for req in criteria.requirements:
            spec_name = req.name.lower()
            spec_value = req.value.lower()
            
            # Direct specification match
            if spec_name in prod_specs:
                norm_value = self._normalize_text(spec_value, target_lang)
                if norm_value in prod_specs[spec_name]:
                    score += 1.0 * req.importance
                    matched_specs.append(f"{req.name}: {req.value}")
                    continue
            
            # Description match
            norm_value = self._normalize_text(spec_value, target_lang)
            if norm_value in desc_norm:
                score += 0.8 * req.importance
                matched_specs.append(f"{req.name}: {req.value}")
                continue
                
            # Spec wasn't found
            missing_specs.append(f"{req.name}: {req.value}")
        
        # Additional free-form text matching from original query
        if criteria.query:
            query_norm = self._normalize_text(criteria.query.lower(), target_lang)
            words = set(query_norm.split())
            desc_words = set(desc_norm.split())
            
            # Calculate word overlap
            overlap = len(words & desc_words) / len(words) if words else 0
            score += overlap * 0.3  # Add up to 0.3 to score for matching query terms
        
        # Normalize final score
        total_importance = sum(req.importance for req in criteria.requirements)
        if total_importance > 0:
            score = score / (total_importance + 0.3)  # +0.3 for query matching
        else:
            score = 0.5  # Neutral score if no requirements
            
        return score, matched_specs, missing_specs

    def _calculate_review_score(self, reviews: List[Review], criteria: SearchCriteria) -> float:
        """Calculate score based on reviews."""
        if not reviews:
            return 0.5
            
        score = 0.0
        total_weight = 0.0
        
        # Normalize query to target language
        target_lang = "en" if criteria.language not in ["hr", "en"] else criteria.language
        query_norm = self._normalize_text(criteria.query.lower(), target_lang)
        query_words = set(query_norm.split())
        
        for review in reviews:
            # Normalize review text
            review_norm = self._normalize_text(review.text.lower(), target_lang)
            review_words = set(review_norm.split())
            
            # Calculate relevance based on word overlap
            overlap = len(query_words & review_words) / len(query_words) if query_words else 0
            
            if overlap > 0:
                # Extract relevant sentences
                sentences = re.split(r'[.!?]', review_norm)
                relevant = [s for s in sentences if any(word in s for word in query_words)]
                review.relevant_points.extend(relevant)
                
                # Calculate weighted score
                weight = overlap * (1.0 if review.rating else 0.5)
                score += (review.rating / 5.0 if review.rating else 0.5) * weight
                total_weight += weight
        
        # Return weighted average or neutral score
        return score / total_weight if total_weight > 0 else 0.5

    def _calculate_price_score(self, price: Optional[float], criteria: SearchCriteria) -> float:
        """Calculate price-based score with budget awareness."""
        if price is None or criteria.budget is None:
            return 0.5
            
        budget = criteria.budget
        
        # Convert currencies if needed (simplified version)
        if criteria.currency != "HRK" and price > 0:
            # Rough conversion rates (should be updated with real API)
            rates = {"EUR": 7.53450, "HRK": 1.0}
            price = price * rates.get(criteria.currency, 1.0)
        
        # Perfect score if price is 70-90% of budget
        if 0.7 * budget <= price <= 0.9 * budget:
            return 1.0
            
        # Good score if price is 50-70% or 90-100% of budget
        if (0.5 * budget <= price < 0.7 * budget) or (0.9 * budget < price <= budget):
            return 0.8
            
        # Lower score if too cheap or over budget
        if price < 0.5 * budget:
            return 0.4
            
        # Over budget
        ratio = budget / price if price > 0 else 0
        return max(0.2, ratio)  # Score decreases as price goes over budget

    def evaluate_products(self, products: List[Product], reviews: Dict[str, List[Review]], criteria: SearchCriteria) -> SearchResult:
        """Evaluate all products and find the best match."""
        if not products:
            raise ValueError("No products to evaluate")
            
        # First analyze the search criteria to extract specifications
        criteria.analyze_query()
        
        scored_products = []
        missing_specs: List[str] = []
        
        for product in products:
            # Calculate specification match score
            spec_score, matched_specs, product_missing_specs = self._calculate_spec_match_score(product, criteria)
            
            # Calculate review score
            review_score = self._calculate_review_score(reviews.get(product.url, []), criteria)
            
            # Calculate price score
            price_score = self._calculate_price_score(product.price, criteria)
            
            # Calculate weighted final score
            # Higher weight on spec matching for specific queries, higher on reviews for general queries
            has_specific_specs = len(criteria.requirements) > 0
            
            if has_specific_specs:
                final_score = (spec_score * 0.5) + (price_score * 0.3) + (review_score * 0.2)
            else:
                final_score = (spec_score * 0.3) + (price_score * 0.3) + (review_score * 0.4)
            
            # Store scores and matched specs
            product.score = final_score
            product.matched_specs = set(matched_specs)
            
            if not scored_products or final_score > scored_products[0].score:
                missing_specs = product_missing_specs
            
            scored_products.append(product)
        
        # Sort by final score
        scored_products.sort(key=lambda x: x.score, reverse=True)
        
        best_product = scored_products[0]
        alternatives = scored_products[1:4]
        
        return SearchResult(
            criteria=criteria,
            best_product=best_product,
            alternative_products=alternatives,
            reviews=reviews.get(best_product.url, []),
            confidence_score=best_product.score,
            matching_specs=list(best_product.matched_specs),
            missing_specs=missing_specs
        )