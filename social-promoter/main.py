from __future__ import annotations

import asyncio
import json
import os
import re
from typing import List, Optional, Any, cast

from dotenv import load_dotenv

import logfire
from pydantic import BaseModel, Field, HttpUrl, TypeAdapter
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerStdio
from pydantic_ai.messages import BinaryContent
from pydantic_ai.models.groq import GroqModel
from pydantic_ai.providers.groq import GroqProvider

# ────────────────────────────────────────────────────────────────────────────────
# Logging & model configuration
# ────────────────────────────────────────────────────────────────────────────────

# Load variables from .env before any config read
load_dotenv(override=True)

logfire.configure()
logfire.instrument_pydantic_ai()

llm_model = GroqModel(
    "meta-llama/llama-4-maverick-17b-128e-instruct",
    provider=GroqProvider(api_key=os.getenv("GROQ_API_KEY", "")),
)

mcp_servers = [
    MCPServerStdio("npx", ["-y", "@modelcontextprotocol/server-memory"]),
    MCPServerStdio(
        "npx",
        ["-y", "firecrawl-mcp"],
        env={"FIRECRAWL_API_KEY": os.getenv("FIRECRAWL_API_KEY", "")},
    ),
]
FIRECRAWL = 1  # index helper

# ────────────────────────────────────────────────────────────────────────────────
# Data models
# ────────────────────────────────────────────────────────────────────────────────

class SearchCriteria(BaseModel, use_attribute_docstrings=True):
    """Criteria extracted from the user prompt."""

    query: str
    budget: float = Field(gt=0)
    currency: str = Field("EUR", pattern="^[A-Z]{3}$")
    location: Optional[str] = None


class Product(BaseModel, use_attribute_docstrings=True):
    name: str
    price: float
    currency: str
    url: HttpUrl
    shop: HttpUrl
    rating: Optional[float] = Field(default=None, ge=0, le=5)


class BestBuyAnswer(BaseModel, use_attribute_docstrings=True):
    product: Product
    reason: str


# ────────────────────────────────────────────────────────────────────────────────
# Helper for decoding BinaryContent
# ────────────────────────────────────────────────────────────────────────────────

def _json_from(content: BinaryContent):
    return json.loads(content.data)


def _text_from(content: BinaryContent) -> str:
    return content.data.decode("utf-8", "ignore")


# ────────────────────────────────────────────────────────────────────────────────
# Tool definitions
# ────────────────────────────────────────────────────────────────────────────────

async def find_shops(criteria: SearchCriteria, limit: int = 10) -> List[HttpUrl]:
    """Return up to `limit` Croatian web‑shop URLs relevant to the query."""
    q = f"{criteria.query} site:.hr kupi OR webshop OR prodaja"
    raw = await mcp_servers[FIRECRAWL].call_tool("firecrawl.search", {"q": q, "limit": limit})
    data = _json_from(raw) if isinstance(raw, BinaryContent) else raw
    results: List[dict[str, Any]] = cast(List[dict[str, Any]], data)
    urls = [item.get("url", "") for item in results if "url" in item]
    return TypeAdapter(List[HttpUrl]).validate_python(urls)


async def scrape_products(shop_url: HttpUrl, criteria: SearchCriteria) -> List[Product]:
    """Scrape products on the given shop page that fit the criteria."""
    raw = await mcp_servers[FIRECRAWL].call_tool("firecrawl.open", {"url": shop_url})
    html = _text_from(raw) if isinstance(raw, BinaryContent) else str(raw)
    products: list[Product] = []
    pattern = re.compile(
        r'<a[^>]+href="(.*?)"[^>]*>(.*?)</a>.*?(\d+[.,]?\d*)\s*(€|eur)',
        re.I | re.S,
    )
    for href, title, price_str, _ in pattern.findall(html):
        price = float(price_str.replace(",", "."))
        if price <= criteria.budget * 1.01:
            url = href if href.startswith("http") else f"{str(shop_url).rstrip('/')}/{href.lstrip('/')}"
            products.append(
                Product(
                    name=re.sub("<.*?>", "", title)[:120],
                    price=price,
                    currency="EUR",
                    url=url,  # type: ignore
                    shop=shop_url,  # type: ignore
                )
            )
    return products


async def find_reviews(product_name: str, max_results: int = 5) -> List[HttpUrl]:
    """Search the web for review URLs of a specific product."""
    q = f"{product_name} recenzija review"
    raw = await mcp_servers[FIRECRAWL].call_tool("firecrawl.search", {"q": q, "limit": max_results})
    data = _json_from(raw) if isinstance(raw, BinaryContent) else raw
    results: List[dict[str, Any]] = cast(List[dict[str, Any]], data)
    urls = [item.get("url", "") for item in results if "url" in item]
    return TypeAdapter(List[HttpUrl]).validate_python(urls)


async def scrape_review(review_url: HttpUrl) -> str:
    """Return plain text of a review page (first 2 000 chars)."""
    raw = await mcp_servers[FIRECRAWL].call_tool("firecrawl.open", {"url": review_url})
    page = _text_from(raw) if isinstance(raw, BinaryContent) else str(raw)
    return re.sub("<.*?>", "", page)[:2000]


# ────────────────────────────────────────────────────────────────────────────────
# Agent instantiation
# ────────────────────────────────────────────────────────────────────────────────

shopping_agent = Agent[
    None,
    BestBuyAnswer,
](
    llm_model,
    tools=[find_shops, scrape_products, find_reviews, scrape_review],
    mcp_servers=mcp_servers,
    output_type=BestBuyAnswer,
    system_prompt=(
        "You are **BestBuy**, a smart Croatian shopping assistant. "
        "Use the tools to find shops, scrape products and reviews, then "
        "return the single best product as `BestBuyAnswer` JSON only."
    ),
)


# ────────────────────────────────────────────────────────────────────────────────
# CLI helper & loop
# ────────────────────────────────────────────────────────────────────────────────

def _parse_criteria(prompt: str) -> SearchCriteria:
    match = re.search(r"(\d+[.,]?\d*)\s*(€|eur|usd|$)", prompt, re.I)
    budget = float(match.group(1).replace(",", ".")) if match else 100.0
    return SearchCriteria(query=prompt, currency="EUR", budget=budget)


async def cli_loop() -> None:
    print("🛒  BestBuy agent – napišite što želite kupiti ('exit' za izlaz)")
    while True:
        user_prompt = input("> ").strip()
        if user_prompt.lower() in {"exit", "quit"}:
            break
        criteria = _parse_criteria(user_prompt)
        hint = f"<<CRITERIA>>\n{criteria.model_dump_json()}\n<<END>>"
        async with shopping_agent.run_mcp_servers():
            result = await shopping_agent.run(user_prompt)
        answer = result.output
        print(
            f"\n✅ Najbolji proizvod: {answer.product.name}\n"
            f"   Cijena : {answer.product.price:.2f} {answer.product.currency}\n"
            f"   Shop   : {answer.product.shop}\n"
            f"   URL    : {answer.product.url}\n"
            f"   Razlog : {answer.reason}\n"
        )


def main() -> None:  # pragma: no cover
    asyncio.run(cli_loop())


if __name__ == "__main__":
    main()
