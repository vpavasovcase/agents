import os
from dotenv import load_dotenv
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Set, Any, Tuple, cast
import re
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential
from openai.types.chat import ChatCompletion
from openai.types.chat.chat_completion import ChatCompletionMessage
from langdetect import detect, LangDetectException
from deep_translator import GoogleTranslator
from openai import AsyncOpenAI
import logging
import json
import logfire
import time
import hashlib
from pydantic_ai import Agent  # For Logfire instrumentation
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

# Configure Logfire
logfire.configure(
    token="pylf_v1_eu_nzHTH6Swg5r0CGHQ2yQyw8jl471wQT023hgtTwMCGgr9",
    send_to_logfire=True,
    environment="development",
    service_name="product-search"
)

def log_token_usage(operation: str, input_tokens: int, output_tokens: int, cache_size: int):
    """Log token usage metrics to Logfire."""
    logger.info(
        "Token usage metrics",
        extra={
            "operation": operation,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "cache_size": cache_size
        }
    )

Agent.instrument_all()

# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

logger.info("Logfire configured with Agent instrumentation")

# Initialize default model configuration
default_model = {
    'name': 'gpt-3.5-turbo-0125',  # Stabilniji model s boljom strukturom
    'provider': 'openai',
    'max_tokens': {
        'analyze_text': 150,      # Povećano za bolje rezultate
        'extract_product': 200,   # Povećano za više detalja
        'analyze_reviews': 120    # Povećano za bolju analizu
    },
    'config': {
        'temperature': 0,
        'top_p': 0.1,
        'frequency_penalty': 0,
        'presence_penalty': 0,
        'response_format': {"type": "json_object"}
    },
    'cache_ttl': 3600  # Cache TTL in seconds (1 hour)
}

class OpenAIModel:
    def __init__(self, model_name: str = default_model['name'], provider: str = default_model['provider']):
        self.model_name = model_name
        self.provider = provider
        self._cache = {}
        logger.info(f"Initialized OpenAI model: {model_name}")
    
    def _get_cache_key(self, text: str, operation: str) -> str:
        """Generate a cache key for the given text and operation."""
        text_hash = hashlib.md5(text.encode()).hexdigest()
        return f"{operation}:{text_hash}"
    
    def _get_from_cache(self, key: str) -> Dict[str, Any]:
        """Get result from cache if it exists and is not expired."""
        if key in self._cache:
            timestamp, data = self._cache[key]
            if time.time() - timestamp < default_model['cache_ttl']:
                logger.info("Cache hit")
                return data
        return {}
    
    def _add_to_cache(self, key: str, data: Dict[str, Any]) -> None:
        """Add result to cache with current timestamp."""
        self._cache[key] = (time.time(), data)
        # Clean old cache entries
        current_time = time.time()
        self._cache = {k: v for k, v in self._cache.items() 
                      if current_time - v[0] < default_model['cache_ttl']}
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def _call_openai_with_retry(
        self, 
        messages: List[Dict[str, str]], 
        max_tokens: int
    ) -> ChatCompletion:
        """Call OpenAI API with retry mechanism."""
        try:
            response = await client.chat.completions.create(
                model=self.model_name,
                messages=[{
                    "role": msg["role"],
                    "content": msg["content"]
                } for msg in messages],
                max_tokens=max_tokens,
                **default_model['config']
            )
            return response
        except Exception as e:
            if "insufficient_quota" in str(e):
                logger.warning("OpenAI API quota exceeded, falling back to basic processing")
                return self._fallback_processing(messages)
            raise

    def _fallback_processing(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """Enhanced fallback when API is not available."""
        user_msg = next((m['content'] for m in messages if m['role'] == 'user'), '').lower()
        specs = []
        product_type = "unknown"
        
        # Product type detection
        product_types = {
            'smartphone': ['mobitel', 'telefon', 'smartphone', 'iphone', 'android'],
            'laptop': ['laptop', 'prijenosnik', 'notebook', 'računalo'],
            'tv': ['tv', 'televizor', 'televizija', 'smart tv'],
            'headphones': ['slušalice', 'headphones', 'bubice', 'airpods'],
            'tablet': ['tablet', 'ipad']
        }
        
        for type_name, keywords in product_types.items():
            if any(word in user_msg for word in keywords):
                product_type = type_name
                specs.append({
                    "name": "type",
                    "value": type_name,
                    "importance": 1.0
                })
                break
        
        # Budget extraction - supporting multiple currencies
        currency_patterns = [
            (r'(\d+(?:,\d+)?(?:\.\d+)?)\s*(?:€|eur[a]?)', 'EUR'),
            (r'(\d+(?:,\d+)?(?:\.\d+)?)\s*(?:kn|kun[ae]|hrk)', 'HRK'),
            (r'(\d+(?:,\d+)?(?:\.\d+)?)\s*(?:USD|\$)', 'USD')
        ]
        
        for pattern, currency in currency_patterns:
            budget_match = re.search(pattern, user_msg)
            if budget_match:
                specs.append({
                    "name": "budget",
                    "value": budget_match.group(1).replace(',', '.'),
                    "currency": currency,
                    "importance": 0.9
                })
                break
        
        # Basic feature extraction
        features = {
            'storage': r'(\d+)\s*(?:gb|tb)',
            'ram': r'(\d+)\s*gb\s*ram',
            'screen': r'(\d+(?:\.\d+)?)\s*(?:inch|"|\'|\s*\')',
            'battery': r'(\d+)\s*mah',
            'color': r'(?:crn[ia]|bijel[ia]|plav[ia]|crven[ia]|zelen[ia]|zlatn[ia]|srebrn[ia])'
        }
        
        for feature, pattern in features.items():
            match = re.search(pattern, user_msg)
            if match:
                specs.append({
                    "name": feature,
                    "value": match.group(1) if match.groups() else match.group(0),
                    "importance": 0.7
                })
        
        result = {
            "specifications": specs,
            "product_type": product_type
        }
        
        logger.info(f"Fallback processing extracted: {len(specs)} specifications")
        return result

    async def analyze_text(self, text: str) -> Dict[str, Any]:
        """Analyze text using OpenAI to extract product requirements."""
        try:
            # Truncate text to reduce tokens
            text = text[:500]
            
            # Check cache first
            cache_key = self._get_cache_key(text, 'analyze_text')
            cached_result = self._get_from_cache(cache_key)
            if cached_result:
                log_token_usage('analyze_text', 0, 0, len(self._cache))
                return cached_result
            
            logger.info(f"Analyzing text: {text[:50]}...")
            
            response = await self._call_openai_with_retry(
                messages=[
                    {
                        "role": "system",
                        "content": "Extract product specs as JSON: {specifications:[{name,value,importance}]}"
                    },
                    {
                        "role": "user", 
                        "content": text
                    }
                ],
                max_tokens=default_model['max_tokens']['analyze_text']
            )
            
            content = response.choices[0].message.content
            if content is None:
                raise ValueError("No content in response")
            
            result = json.loads(content)
            self._add_to_cache(cache_key, result)
            
            # Log token usage
            input_tokens = len(text.split())
            output_tokens = len(content.split())
            log_token_usage('analyze_text', input_tokens, output_tokens, len(self._cache))
            
            logger.info("Successfully analyzed text")
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing text: {str(e)}")
            return {
                "error": str(e),
                "product_type": "unknown",
                "specifications": []
            }

    async def extract_product_info(self, html_content: str) -> Dict[str, Any]:
        """Extract product information from HTML content."""
        try:
            # Truncate and clean HTML content
            html_content = re.sub(r'\s+', ' ', html_content[:800])
            
            # Check cache
            cache_key = self._get_cache_key(html_content, 'extract_product')
            cached_result = self._get_from_cache(cache_key)
            if cached_result:
                log_token_usage('extract_product', 0, 0, len(self._cache))
                return cached_result
            
            response = await self._call_openai_with_retry(
                messages=[
                    {
                        "role": "system",
                        "content": "Extract: {name,price,specs}"
                    },
                    {
                        "role": "user",
                        "content": html_content
                    }
                ],
                max_tokens=default_model['max_tokens']['extract_product']
            )
            
            content = response.choices[0].message.content
            if content is None:
                raise ValueError("No content in response")
            
            result = json.loads(content)
            self._add_to_cache(cache_key, result)
            
            # Log token usage
            input_tokens = len(html_content.split())
            output_tokens = len(content.split())
            log_token_usage('extract_product', input_tokens, output_tokens, len(self._cache))
            
            return result
            
        except Exception as e:
            logger.error(f"Error extracting product info: {str(e)}")
            return {
                "error": str(e),
                "name": "",
                "price": 0,
                "specifications": {}
            }
    
    async def analyze_reviews(self, reviews: List[str]) -> Dict[str, Any]:
        """Analyze product reviews for sentiment and key points."""
        try:
            # Take only first 3 reviews and limit each review length
            reviews = [review[:200] for review in reviews[:3]]
            combined_reviews = " | ".join(reviews)
            
            # Check cache
            cache_key = self._get_cache_key(combined_reviews, 'analyze_reviews')
            cached_result = self._get_from_cache(cache_key)
            if cached_result:
                log_token_usage('analyze_reviews', 0, 0, len(self._cache))
                return cached_result
            
            response = await self._call_openai_with_retry(
                messages=[
                    {
                        "role": "system",
                        "content": "Return {sentiment,key_points[]}"
                    },
                    {
                        "role": "user",
                        "content": combined_reviews
                    }
                ],
                max_tokens=default_model['max_tokens']['analyze_reviews']
            )
            
            content = response.choices[0].message.content
            if content is None:
                raise ValueError("No content in response")
            
            result = json.loads(content)
            self._add_to_cache(cache_key, result)
            
            # Log token usage
            input_tokens = sum(len(review.split()) for review in reviews)
            output_tokens = len(content.split())
            log_token_usage('analyze_reviews', input_tokens, output_tokens, len(self._cache))
            
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing reviews: {str(e)}")
            return {
                "error": str(e),
                "sentiment": "neutral",
                "key_points": []
            }

class ProductSpecification(BaseModel):
    name: str
    value: str
    importance: float = 1.0

class Product(BaseModel):
    name: str
    price: float
    currency: str
    url: str
    shop_url: str
    description: Optional[str] = None
    specifications: Dict[str, str] = {}
    matched_specs: Set[str] = set()
    score: float = 0.0

class Review(BaseModel):
    product_url: str
    text: str
    rating: Optional[float] = None
    source: str
    date: Optional[str] = None
    relevant_points: List[str] = []

class SearchCriteria(BaseModel):
    query: str
    language: str = "hr"
    budget: Optional[float] = None
    currency: str = "HRK"
    requirements: List[ProductSpecification] = []
    
    @validator('budget')
    def validate_budget(cls, v):
        if v is not None and v <= 0:
            raise ValueError("Budget must be positive")
        return v
        
    @classmethod
    async def from_text(cls, text: str) -> 'SearchCriteria':
        """Create SearchCriteria from free-form text using OpenAI."""
        try:
            logger.info(f"Creating search criteria from: {text[:100]}...")
            
            # Create basic criteria with query
            criteria = cls(query=text)
            
            # First detect language
            try:
                lang = detect(text)
                criteria.language = lang
                logger.info(f"Detected language: {lang}")
            except LangDetectException:
                logger.warning("Could not detect language, using default")
            
            # Extract budget using regex first
            budget_patterns = [
                r'(\d+(?:,\d+)?(?:\.\d+)?)\s*(?:kn|kun[ae]|hrk|kuna)',  # Croatian Kuna
                r'(\d+(?:,\d+)?(?:\.\d+)?)\s*(?:€|eur[a]?)',  # Euro
                r'(\d+(?:,\d+)?(?:\.\d+)?)\s*(?:USD|\$)'  # USD
            ]
            
            for pattern in budget_patterns:
                budget_match = re.search(pattern, text.lower())
                if budget_match:
                    value = float(budget_match.group(1).replace(',', '.'))
                    criteria.budget = value
                    # Set appropriate currency
                    if 'kn' in pattern or 'hrk' in pattern:
                        criteria.currency = 'HRK'
                    elif '€' in pattern or 'eur' in pattern:
                        criteria.currency = 'EUR'
                    elif 'USD' in pattern or '$' in pattern:
                        criteria.currency = 'USD'
                    logger.info(f"Extracted budget: {value} {criteria.currency}")
                    break
            
            # Then analyze with OpenAI
            analysis = await OpenAIModel().analyze_text(text)
            
            # Add extracted specifications if available
            if isinstance(analysis, dict) and 'specifications' in analysis:
                specs = analysis.get('specifications', [])
                if isinstance(specs, list) and specs:  # Check if specs is non-empty list
                    for spec in specs:
                        if isinstance(spec, dict) and 'name' in spec and 'value' in spec:
                            spec_obj = ProductSpecification(
                                name=spec.get('name', '').strip(),
                                value=spec.get('value', '').strip(),
                                importance=float(spec.get('importance', 1.0))
                            )
                            if spec_obj.name and spec_obj.value:  # Only add if both name and value are non-empty
                                criteria.requirements.append(spec_obj)
                                logger.info(f"Added specification: {spec_obj}")
            
            logger.info(f"Created search criteria with {len(criteria.requirements)} requirements")
            return criteria
            
        except Exception as e:
            logger.error(f"Failed to create search criteria: {str(e)}")
            # Return basic criteria if analysis fails
            return cls(query=text)
    
    def _detect_language(self, text: str) -> str:
        """Detect text language."""
        try:
            return detect(text)
        except LangDetectException:
            return self.language

    def _translate_to_english(self, text: str) -> str:
        """Translate text to English if needed."""
        lang = self._detect_language(text)
        if lang != "en":
            translator = GoogleTranslator(source=lang, target='en')
            return translator.translate(text)
        return text

class SearchResult(BaseModel):
    criteria: SearchCriteria
    best_product: Optional[Product] = None
    alternative_products: List[Product] = []
    reviews: List[Review] = []
    confidence_score: float = 0.0
    matching_specs: List[str] = []
    missing_specs: List[str] = []