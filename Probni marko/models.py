from pydantic import BaseModel
from typing import List, Optional, Dict

class Product(BaseModel):
    name: str
    price: float
    currency: str
    url: str
    shop_url: str
    description: Optional[str] = None
    specifications: Optional[Dict[str, str]] = None

class Review(BaseModel):
    product_url: str
    text: str
    rating: Optional[float] = None
    source: str
    date: Optional[str] = None

class SearchCriteria(BaseModel):
    product_type: str
    budget: float
    currency: str = "EUR"
    location: Optional[str] = None
    delivery_time: Optional[str] = None

class SearchResult(BaseModel):
    criteria: SearchCriteria
    best_product: Product
    alternative_products: List[Product]
    reviews: List[Review]
    confidence_score: float