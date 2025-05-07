import os
import asyncio
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
import logfire
from openai import OpenAI
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from memory_client import MemoryClient, Entity, Relation

# Initialize logfire
logfire.configure()
logger = logfire.getLogger(__name__)

# Setup OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Define Pydantic models for structured data
class ProductScore(BaseModel):
    product_id: str
    product_name: str
    webshop_name: str
    price: float
    currency: str = "EUR"
    overall_score: float = Field(..., ge=0, le=10)
    review_score: float = Field(..., ge=0, le=10)
    features_score: float = Field(..., ge=0, le=10)
    price_value_score: float = Field(..., ge=0, le=10)
    requirements_match_score: float = Field(..., ge=0, le=10)
    url: str
    explanation: str

class EvaluationResult(BaseModel):
    best_product: ProductScore
    all_products: List[ProductScore]
    requirements: List[str]
    budget: float
    currency: str = "EUR"
    evaluation_summary: str

class EvaluationAgent:
    def __init__(self):
        # Initialize LLM
        self.llm = ChatOpenAI(temperature=0, model="gpt-4o")
        
        # Initialize memory client
        self.memory_client = MemoryClient()
        
        logger.info("EvaluationAgent initialized")

    async def evaluate_products(self, product_query: str, budget: float, requirements: List[str]) -> EvaluationResult:
        """Evaluate all products found by the webcrawl agent and determine the best one."""
        logger.info(f"Evaluating products for: {product_query} with budget {budget}")
        
        # Retrieve all products from memory
        product_entities = await self.memory_client.get_entities_by_type("product")
        logger.info(f"Retrieved {len(product_entities)} products from memory")
        
        # Filter products that are within budget
        products_within_budget = [p for p in product_entities if p.properties.get("price", float('inf')) <= budget]
        logger.info(f"{len(products_within_budget)} products are within budget")
        
        if not products_within_budget:
            logger.warning("No products found within budget!")
            return None
        
        # For each product, get its features and reviews
        product_details = []
        
        for product in products_within_budget:
            product_id = product.id
            
            # Get features
            feature_relations = await self.memory_client.get_relations_by_source_and_type(product_id, "has_feature")
            features = []
            
            for relation in feature_relations:
                feature_entity = await self.memory_client.get_entity(relation.target_id)
                if feature_entity:
                    features.append({
                        "name": feature_entity.properties.get("name", ""),
                        "value": feature_entity.properties.get("value", "")
                    })
            
            # Get reviews
            review_relations = await self.memory_client.get_relations_by_source_and_type(product_id, "has_review")
            reviews = []
            
            for relation in review_relations:
                review_entity = await self.memory_client.get_entity(relation.target_id)
                if review_entity:
                    reviews.append({
                        "source": review_entity.properties.get("source", ""),
                        "author": review_entity.properties.get("author", ""),
                        "rating": review_entity.properties.get("rating", 0),
                        "content": review_entity.properties.get("content", ""),
                        "pros": review_entity.properties.get("pros", []),
                        "cons": review_entity.properties.get("cons", [])
                    })
            
            # Add product with its features and reviews to the list
            product_details.append({
                "id": product_id,
                "name": product.properties.get("name", ""),
                "brand": product.properties.get("brand", ""),
                "model": product.properties.get("model", ""),
                "price": product.properties.get("price", 0),
                "currency": product.properties.get("currency", "EUR"),
                "url": product.properties.get("url", ""),
                "webshop_name": product.properties.get("webshop_name", ""),
                "description": product.properties.get("description", ""),
                "features": features,
                "reviews": reviews
            })
        
        # Score each product
        products_scores = await self._score_products(product_details, requirements, budget)
        
        # Find the best product
        if products_scores:
            best_product = max(products_scores, key=lambda x: x.overall_score)
            
            # Create evaluation result
            evaluation_result = EvaluationResult(
                best_product=best_product,
                all_products=products_scores,
                requirements=requirements,
                budget=budget,
                currency="EUR",
                evaluation_summary=await self._generate_evaluation_summary(best_product, products_scores, requirements, budget)
            )
            
            logger.info(f"Evaluation complete. Best product: {best_product.product_name} with score {best_product.overall_score}")
            return evaluation_result
        else:
            logger.warning("No products could be scored!")
            return None

    async def _score_products(self, products: List[Dict], requirements: List[str], budget: float) -> List[ProductScore]:
        """Score each product based on reviews, features, price-value ratio, and requirements match."""
        logger.info(f"Scoring {len(products)} products")
        
        products_scores = []
        
        for product in products:
            # Calculate review score
            review_score = await self._calculate_review_score(product["reviews"])
            
            # Calculate features score and requirements match
            features_score, requirements_match_score = await self._evaluate_features(product["features"], requirements)
            
            # Calculate price-value score (higher scores for better value