# best_buy_agent.py

import asyncio
import os
import json
import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

# PydanticAI Imports
from pydantic_ai import Agent, tool, RunContext
from pydantic_ai.models.groq import GroqModel
from pydantic_ai.providers.groq import GroqProvider
from pydantic_ai.mcp import MCPServerStdio
from typing import Union


# Logging Imports
import logfire

# Environment Variables
from dotenv import load_dotenv

# Učitaj varijable iz .env datoteke na početku
load_dotenv(override=True)

# --- Konfiguracija Logfire ---
logfire_token = os.getenv("LOGFIRE_TOKEN")
if not logfire_token:
    print("UPOZORENJE: LOGFIRE_TOKEN nije pronađen u .env datoteci. Logiranje na Logfire platformu je onemogućeno.")
    # Odlučite želite li nastaviti bez tokena ili prekinuti
    # raise ValueError("LOGFIRE_TOKEN nije postavljen!")

logfire.configure(
    token=logfire_token,
    send_to_logfire=bool(logfire_token) # Šalji samo ako token postoji
    # Možete dodati druge konfiguracijske opcije ovdje
    # pydantic_plugin = logfire.PydanticPlugin(log_all=True),
)
# logfire.instrument() # Pokušaj općenitog instrumentiranja

print(f"Logfire konfiguriran. Slanje logova: {'Aktivno' if logfire_token else 'Neaktivno'}")

# Groq API configuration
groq_api_key = os.getenv("GROQ_API_KEY")
if not groq_api_key:
    raise ValueError("GROQ_API_KEY nije postavljen u .env datoteci!")

# Zamijenjena linija za direktno korištenje GroqModel s navedenim modelom
llm_model = GroqModel('meta-llama/llama-4-maverick-17b-128e-instruct', provider=GroqProvider(api_key=os.getenv('GROQ_API_KEY')))


# --- Pydantic Modeli za Strukturiranje Podataka ---

class Product(BaseModel):
    """Predstavlja proizvod pronađen na webshopu."""
    name: str = Field(..., description="Naziv proizvoda")
    price: Optional[float] = Field(None, description="Cijena proizvoda (u EUR)")
    currency: Optional[str] = Field("EUR", description="Valuta cijene")
    url: str = Field(..., description="URL stranice proizvoda na webshopu")
    webshop_url: str = Field(..., description="URL webshopa gdje je proizvod pronađen")
    description: Optional[str] = Field(None, description="Kratki opis ili specifikacije proizvoda")

class Review(BaseModel):
    """Predstavlja recenziju proizvoda."""
    product_name: str = Field(..., description="Naziv proizvoda na koji se recenzija odnosi")
    source_url: str = Field(..., description="URL izvora recenzije")
    rating: Optional[float] = Field(None, description="Numerička ocjena (npr. 1-5), ako je dostupna")
    summary: Optional[str] = Field(None, description="Sažetak ili ključni dijelovi recenzije")
    raw_content: Optional[str] = Field(None, description="Sirovi tekst recenzije (opcionalno)")

class Webshop(BaseModel):
    """Predstavlja webshop."""
    name: Optional[str] = Field(None, description="Naziv webshopa")
    url: str = Field(..., description="Glavni URL webshopa")

class FinalResult(BaseModel):
    """Strukturirani konačni odgovor korisniku."""
    recommended_product: Optional[Product] = Field(None, description="Preporučeni 'best buy' proizvod.")
    justification: str = Field(..., description="Obrazloženje zašto je ovaj proizvod preporučen.")
    alternative_products: List[Product] = Field([], description="Lista alternativnih dobrih opcija.")
    message: str = Field(..., description="Poruka korisniku koja sažima nalaze.")

# --- MCP Server Konfiguracija ---

# !!! VAŽNO: Zamijenite ove placeholder naredbe s PRAVIM naredbama ili URL-ovima za vaše MCP servere !!!

# Konfiguracija Memory MCP servera
MEMORY_MCP_COMMAND = ['npx', '-y', '@mendable/memory-mcp-server', 'stdio']

# Firecrawl MCP konfiguracija
FIRECRAWL_MCP_COMMAND = ['npx', '-y', '@mendable/firecrawl-mcp-server', 'stdio']

# Alternativa: Ako serveri rade zasebno na nekim URL-ovima
# MEMORY_MCP_URL = "http://localhost:8001" # Primjer URL-a
# FIRECRAWL_MCP_URL = "http://localhost:8002" # Primjer URL-a

mcp_servers = []

try:
    # Konfiguriraj Memory MCP server
    print("Konfiguriranje Memory MCP servera putem stdio...")
    memory_server = MCPServerStdio('memory-server', MEMORY_MCP_COMMAND)
    mcp_servers.append(memory_server)
    print("Memory MCP server dodan u konfiguraciju.")

    # Konfiguriraj Firecrawl MCP server
    print("Konfiguriranje Firecrawl MCP servera putem stdio...")
    firecrawl_server = MCPServerStdio('firecrawl', FIRECRAWL_MCP_COMMAND)
    mcp_servers.append(firecrawl_server)
    print("Firecrawl MCP server dodan u konfiguraciju.")


except Exception as e:
    logfire.error(f"Greška pri konfiguraciji MCP servera: {e}", exc_info=True)
    print(f"Greška pri konfiguraciji MCP servera: {e}. Agent možda neće imati sve funkcionalnosti.")


# --- Definiranje Alata za Agenta ---

@tool
async def search_webshops(query: str, location: Optional[str] = None, num_results: int = 5) -> List[str]:
    """
    Pretražuje web za webshopove koji prodaju određeni tip proizvoda, opcionalno uzimajući u obzir lokaciju.
    Vraća listu URL-ova pronađenih webshopova.
    :param query: Opis proizvoda koji se traži (npr. 'bluetooth slušalice za android')
    :param location: Lokacija relevantna za pretragu (npr. 'Hrvatska')
    :param num_results: Maksimalan broj rezultata (URL-ova webshopova) za vratiti.
    """
    logfire.info(f"Pokretanje pretrage webshopova za: '{query}' u '{location}'")
    # TODO: Implementirati stvarnu logiku pretrage (npr. Google Search API, SerpApi).
    print(f"SIMULACIJA PRETRAGE WEBSHOPOVA za: '{query}' lokacija: '{location}'")
    # Placeholder URL-ovi:
    await asyncio.sleep(1) # Simulacija odgode
    placeholder_urls = [
        f"https://placeholder-shop1-{location or 'global'}.com/{query.replace(' ', '-')}",
        f"https://placeholder-shop2-{location or 'global'}.com/search?q={query.replace(' ', '+')}",
        f"https://tech-store-{location or 'global'}.example/products/{query.split(' ')[0]}",
    ]
    final_urls = placeholder_urls[:num_results]
    logfire.info(f"Placeholder - Pronađeni URL-ovi webshopova: {final_urls}")
    return final_urls

@tool
async def crawl_webshop_for_products(url: str, product_type: str, budget: float, criteria: Optional[str] = None) -> List[Product]:
    """
    Koristi Firecrawl MCP server za scrapanje webshopa na danom URL-u.
    Traži proizvode koji odgovaraju tipu proizvoda, budžetu i opcionalnim kriterijima.
    Implicitno bi trebao spremiti pronađene proizvode koristeći Memory MCP server (ako je konfiguriran i PydanticAI to podržava).
    :param url: URL webshopa za scrapanje.
    :param product_type: Tip proizvoda koji se traži (npr. 'bluetooth slušalice').
    :param budget: Maksimalni budžet korisnika.
    :param criteria: Dodatni kriteriji (npr. 'za android', 'vodootporne').
    :return: Lista pronađenih i filtriranih Product objekata (za internu upotrebu agenta).
    """
    logfire.info(f"Pokretanje crawl-a webshopa: {url} za '{product_type}' (budžet: {budget} EUR, kriteriji: '{criteria}')")
    print(f"AGENT ACTION: Zahtjev za crawl webshopa {url} poslan Firecrawl MCP.")
    print(f"AGENT ACTION: Očekuje se da Firecrawl pronađe proizvode. Potrebno ih je zatim filtrirati i SPREMITI U MEMORIJU (ako je dostupna).")

    # Koristimo Firecrawl za scrapanje stranice
    found_products = []
    try:
        # Definiraj query za Firecrawl koji će prepoznati proizvode
        crawl_query = {
            "url": url,
            "search": product_type,
            "extractFields": {
                "name": "string",
                "price": "number",
                "description": "string",
                "productUrl": "url"
            }
        }

        # Pozovi Firecrawl kroz PydanticAI MCP
        crawl_result = await agent.mcp_request('firecrawl', 'crawl', crawl_query)

        # Pretvori rezultate u Product objekte
        for item in crawl_result.get('items', []):
            try:
                # Pretvori cijenu u EUR ako je potrebno (TODO: implementirati konverziju valuta)
                price = float(item.get('price', 0))

                product = Product(
                    name=item.get('name', ''),
                    price=price,
                    url=item.get('productUrl', '') or f"{url}/product",
                    webshop_url=url,
                    description=item.get('description', '')
                )
                found_products.append(product)
            except (ValueError, TypeError) as e:
                logfire.warning(f"Preskačem proizvod zbog greške u parsiranju: {e}")
                continue
    except Exception as e:
        logfire.error(f"Greška pri crawlanju webshopa {url}: {e}")
        # Nastavi s praznom listom ako crawl ne uspije
    filtered_products = [p for p in found_products if p.price is not None and p.price <= budget]
    logfire.info(f"Placeholder - Pronađeni i filtrirani proizvodi na {url}: {filtered_products}")

    # Spremi proizvode u Memory MCP
    for product in filtered_products:
        try:
            memory_entry = {
                "type": "product",
                "data": product.dict(),
                "metadata": {
                    "source_url": url,
                    "crawl_timestamp": str(datetime.datetime.now()),
                    "product_type": product_type,
                    "criteria": criteria
                }
            }
            await agent.mcp_request('memory-server', 'save', memory_entry)
            logfire.info(f"Proizvod '{product.name}' uspješno spremljen u memoriju")
        except Exception as e:
            logfire.error(f"Greška pri spremanju proizvoda '{product.name}' u memoriju: {e}")
            continue

    return filtered_products

@tool
async def search_product_reviews(product_name: str, num_results: int = 3) -> List[str]:
    """
    Pretražuje web za recenzije specifičnog proizvoda.
    Vraća listu URL-ova pronađenih recenzija.
    :param product_name: Naziv proizvoda za koji se traže recenzije.
    :param num_results: Maksimalan broj URL-ova recenzija za vratiti.
    """
    logfire.info(f"Pokretanje pretrage recenzija za: '{product_name}'")
    urls = []
    try:
        # Koristi Firecrawl za pretragu recenzija
        search_query = {
            "keywords": [f"{product_name} review", f"{product_name} recenzija"],
            "sites": [
                "youtube.com",
                "nabava.net",
                "bug.hr",
                "forum.hr"
            ],
            "limit": num_results
        }

        search_results = await agent.mcp_request('firecrawl', 'search', search_query)

        # Filtriraj i obradi rezultate
        for result in search_results.get('results', []):
            url = result.get('url')
            if url and len(urls) < num_results:
                urls.append(url)

        if not urls:
            logfire.warning(f"Nisu pronađene recenzije za '{product_name}'")

    except Exception as e:
        logfire.error(f"Greška pri pretrazi recenzija za '{product_name}': {e}")

    logfire.info(f"Pronađeni URL-ovi recenzija: {urls}")
    return urls

@tool
async def crawl_review_page(url: str, product_name: str) -> Optional[Review]:
    """
    Koristi Firecrawl MCP server za scrapanje stranice s recenzijom na danom URL-u.
    Pokušava ekstrahirati ocjenu i sažetak recenzije.
    Implicitno bi trebao spremiti pronađenu recenziju koristeći Memory MCP server, povezujući je s proizvodom.
    :param url: URL stranice s recenzijom.
    :param product_name: Naziv proizvoda na koji se recenzija odnosi.
    :return: Review objekt ili None ako ekstrakcija ne uspije.
    """
    logfire.info(f"Pokretanje crawl-a recenzije: {url} za '{product_name}'")
    print(f"AGENT ACTION: Zahtjev za crawl recenzije {url} poslan Firecrawl MCP.")
    print(f"AGENT ACTION: Očekuje se da Firecrawl scrapa sadržaj. Potrebno ga je parsirati (ocjena, sažetak) i SPREMITI U MEMORIJU (ako je dostupna).")

    content = None
    summary = None
    rating = None
    try:
        # Koristi Firecrawl za dohvat sadržaja recenzije
        crawl_query = {
            "url": url,
            "extractFields": {
                "rating": "number",
                "content": "text",
                "title": "string"
            },
            "selectors": {
                "rating": ["span.rating", ".review-score", "[itemprop='ratingValue']"],
                "content": ["div.review-content", "article", ".user-review"],
                "title": ["h1", ".review-title"]
            }
        }

        crawl_result = await agent.mcp_request('firecrawl', 'crawl', crawl_query)

        # Koristi LLM za generiranje sažetka iz crawlanog sadržaja
        content = crawl_result.get('content', '')
        if content:
            summary_prompt = f"Sažmi ovu recenziju proizvoda {product_name} u 2-3 rečenice:\n\n{content}"
            summary_result = await agent.llm.complete(summary_prompt)
            summary = summary_result.choices[0].text.strip()

        # Pokušaj izvući ocjenu iz crawlanog sadržaja
        rating_text = crawl_result.get('rating')
        if rating_text:
            try:
                # Pokušaj pretvoriti različite formate ocjena u broj od 0-5
                rating_num = float(rating_text)
                if rating_num > 5:  # Ako je ocjena npr. 0-100
                    rating = rating_num / 20  # Pretvori u 0-5
                elif rating_num > 0:  # Ako je već 0-5
                    rating = rating_num
            except (ValueError, TypeError):
                pass  # Ako ne uspije parsiranje, ostavi rating kao None

    except Exception as e:
        logfire.error(f"Greška pri crawlanju recenzije s {url}: {e}")

    review = Review(
        product_name=product_name,
        source_url=url,
        rating=rating,
        summary=summary,
        raw_content=content if content else None
    )
    logfire.info(f"Scrapirana recenzija s {url}: Rating={review.rating}, Summary='{review.summary[:50] if review.summary else 'None'}...'")

    # Spremi recenziju u Memory MCP
    try:
        memory_entry = {
            "type": "review",
            "data": review.dict(),
            "metadata": {
                "product_name": product_name,
                "source_url": url,
                "crawl_timestamp": str(datetime.datetime.now())
            }
        }
        await agent.mcp_request('memory-server', 'save', memory_entry)
        logfire.info(f"Recenzija za '{product_name}' uspješno spremljena u memoriju")
    except Exception as e:
        logfire.error(f"Greška pri spremanju recenzije u memoriju: {e}")

    return review

@tool
async def retrieve_products_from_memory() -> List[Product]:
    """
    Dohvaća sve Product objekte spremljene u memoriji.
    """
    logfire.info("Dohvaćanje proizvoda iz memorije...")
    print("AGENT ACTION: Zahtjev za dohvat svih proizvoda iz Memory MCP.")
    # TODO: Implementirati stvarni poziv prema Memory MCP serveru.
    #       Očekuje se povrat liste Product objekata.

    try:
        # Dohvati sve proizvode iz memorije
        memory_query = {
            "type": "product",
            "limit": 100  # Maksimalan broj proizvoda za dohvatiti
        }

        memory_results = await agent.mcp_request('memory-server', 'query', memory_query)

        products = []
        for item in memory_results.get('items', []):
            try:
                product_data = item.get('data', {})
                product = Product(**product_data)
                products.append(product)
            except Exception as e:
                logfire.warning(f"Nije moguće parsirati proizvod iz memorije: {e}")
                continue

        logfire.info(f"Uspješno dohvaćeno {len(products)} proizvoda iz memorije")
        return products

    except Exception as e:
        logfire.error(f"Greška pri dohvaćanju proizvoda iz memorije: {e}")
        return []  # Vrati praznu listu u slučaju greške

@tool
async def retrieve_reviews_for_product(product_name: str) -> List[Review]:
    """
    Dohvaća sve Review objekte iz memorije povezane s određenim proizvodom.
    """
    logfire.info(f"Dohvaćanje recenzija iz memorije za: '{product_name}'")
    print(f"AGENT ACTION: Zahtjev za dohvat recenzija za '{product_name}' iz Memory MCP.")
    # TODO: Implementirati stvarni poziv prema Memory MCP serveru.
    #       Očekuje se povrat liste Review objekata za zadani product_name.

    try:
        # Dohvati recenzije za određeni proizvod iz memorije
        memory_query = {
            "type": "review",
            "metadata": {
                "product_name": product_name
            }
        }

        memory_results = await agent.mcp_request('memory-server', 'query', memory_query)

        reviews = []
        for item in memory_results.get('items', []):
            try:
                review_data = item.get('data', {})
                review = Review(**review_data)
                reviews.append(review)
            except Exception as e:
                logfire.warning(f"Nije moguće parsirati recenziju iz memorije: {e}")
                continue

        logfire.info(f"Uspješno dohvaćeno {len(reviews)} recenzija za '{product_name}' iz memorije")
        return reviews

    except Exception as e:
        logfire.error(f"Greška pri dohvaćanju recenzija iz memorije: {e}")
        return []  # Vrati praznu listu u slučaju greške


@tool
async def evaluate_products(budget: float, criteria: Optional[str] = None) -> FinalResult:
    """
    Analizira sve prikupljene proizvode i njihove recenzije iz memorije kako bi odabrao 'best buy'.
    Uzima u obzir budžet i originalne kriterije korisnika.
    :param budget: Maksimalni budžet korisnika.
    :param criteria: Originalni kriteriji korisnika.
    :return: FinalResult objekt s preporukom i obrazloženjem.
    """
    logfire.info(f"Pokretanje evaluacije proizvoda (Budžet: {budget} EUR, Kriteriji: '{criteria}')")
    all_products = []
    try:
        all_products = await retrieve_products_from_memory()
        if not all_products:
            msg = "Nisam pronašao proizvode u memoriji za evaluaciju."
            if not mcp_servers or 'memory-server' not in str(mcp_servers):
                 msg += " (Memory MCP nije konfiguriran)"
            logfire.warning(msg)
            return FinalResult(
                message=msg,
                justification="Nema dostupnih podataka.",
                recommended_product=None,
                alternative_products=[]
            )
    except Exception as e:
        logfire.error(f"Greška pri dohvaćanju proizvoda za evaluaciju: {e}", exc_info=True)
        return FinalResult(
            message="Došlo je do greške prilikom dohvaćanja podataka.",
            justification=f"Greška: {e}",
            recommended_product=None,
            alternative_products=[]
        )

    products_in_budget = [p for p in all_products if p.price is not None and p.price <= budget]
    if not products_in_budget:
         logfire.warning(f"Nema proizvoda unutar budžeta {budget} EUR.")
         # Vraćamo sve pronađene kao alternativu ako su skuplji
         alternative_prods = sorted(all_products, key=lambda p: p.price if p.price else float('inf'))
         return FinalResult(
             message=f"Nisam pronašao proizvode unutar vašeg budžeta od {budget} EUR.",
             justification="Svi pronađeni proizvodi su skuplji.",
             alternative_products=alternative_prods[:3] # Prikaži najjeftinije od skupljih
        )

    product_scores: Dict[str, Dict[str, Any]] = {}
    for product in products_in_budget:
        reviews = []
        try:
            reviews = await retrieve_reviews_for_product(product.name)
        except Exception as e:
             logfire.error(f"Greška pri dohvaćanju recenzija za '{product.name}': {e}")

        valid_reviews = [r for r in reviews if r.rating is not None]
        ratings = [r.rating for r in valid_reviews if r.rating is not None]
        avg_rating = sum(ratings) / len(ratings) if ratings else None
        num_reviews = len(reviews)
        product_scores[product.url] = {
            "product": product,
            "avg_rating": avg_rating,
            "num_reviews": num_reviews,
            "score": 0.0 # Placeholder
        }
        logfire.info(f"Evaluacija za '{product.name}': Avg Rating={avg_rating}, Reviews={num_reviews}")

    # Algoritam ocjenjivanja (primjer - treba poboljšati)
    best_product_url = None
    highest_score = -1.0

    for url, data in product_scores.items():
        score = 0.0
        # Osnovna ocjena po ratingu i broju recenzija
        if data["avg_rating"] is not None:
            score += data["avg_rating"] * 0.7
        score += min(data["num_reviews"], 5) * 0.06 # Bonus za recenzije (do 0.3)
        # TODO: Poboljšati skor - analiza kriterija, cijene u odnosu na budžet itd.
        # Npr. manji postotak budžeta = veći bonus?
        # Npr. LLM analiza product.description vs criteria?
        score -= (data["product"].price / budget) * 0.1 # Mali penal za skuplje unutar budžeta

        data["score"] = score
        logfire.info(f"Konačni skor za '{data['product'].name}': {score:.2f}")
        if score > highest_score:
            highest_score = score
            best_product_url = url

    # Pripremi konačni rezultat
    if best_product_url and best_product_url in product_scores:
        best_product_data = product_scores[best_product_url]
        recommended = best_product_data["product"]
        # Sortiraj ostale po skoru za alternative
        alternatives = sorted(
            [data["product"] for url, data in product_scores.items() if url != best_product_url],
            key=lambda p: product_scores[p.url]["score"],
            reverse=True
        )
        justification = f"Preporučujem '{recommended.name}' (cijena: {recommended.price} EUR). Ima najbolji izračunati skor ({highest_score:.2f}) temeljen na prosječnoj ocjeni ({best_product_data['avg_rating'] or 'N/A'}) i broju recenzija ({best_product_data['num_reviews']}), unutar vašeg budžeta."
        if criteria:
            justification += f" Provjerite specifikacije na linku da vidite odgovara li kriteriju: '{criteria}'."
        if not best_product_data['avg_rating'] and best_product_data['num_reviews'] == 0:
             justification += " Napomena: Nisu pronađene recenzije, preporuka se temelji primarno na cijeni i dostupnosti."
        message = f"Najbolji izbor za vas unutar {budget} EUR čini se da je {recommended.name}."
        return FinalResult(recommended_product=recommended, justification=justification, alternative_products=alternatives[:2], message=message)
    elif products_in_budget: # Fallback ako nema skora - najjeftiniji
        cheapest_product = min(products_in_budget, key=lambda p: p.price if p.price is not None else float('inf'))
        logfire.warning("Nije bilo moguće izračunati smislen skor, preporučujem najjeftiniji proizvod.")
        return FinalResult(
            recommended_product=cheapest_product,
            justification=f"Nisam mogao izračunati ocjene, ali '{cheapest_product.name}' je najjeftinija opcija ({cheapest_product.price} EUR) unutar budžeta.",
            alternative_products=[p for p in products_in_budget if p.url != cheapest_product.url][:2],
            message=f"Najpovoljnija opcija unutar {budget} EUR je {cheapest_product.name}."
        )
    else: # Should not happen if checks above work
         logfire.error("Neočekivano stanje u evaluaciji - nema proizvoda za preporuku.")
         return FinalResult(
             message="Nisam uspio odrediti najbolji proizvod.",
             justification="Došlo je do greške u evaluaciji.",
             recommended_product=None,
             alternative_products=[]
         )


@tool
async def clear_memory() -> str:
    """
    Briše sve podatke (proizvode, recenzije, webshopove) iz Memory MCP servera.
    """
    logfire.warning("Brisanje podataka iz memorije...")
    print("AGENT ACTION: Zahtjev za brisanje svih podataka iz Memory MCP.")
    try:
        if not mcp_servers or 'memory-server' not in str(mcp_servers):
            msg = "Memorija nije aktivno konfigurirana, preskačem brisanje."
            print(f"INFO: {msg}")
            return msg

        # Pošalji zahtjev za brisanje svih podataka
        clear_result = await agent.mcp_request('memory-server', 'clear', {})

        if clear_result.get('success', False):
            msg = "Memorija je uspješno obrisana."
            logfire.info(msg)
            return msg
        else:
            msg = f"Greška pri brisanju memorije: {clear_result.get('error', 'Nepoznata greška')}"
            logfire.error(msg)
            return msg

    except Exception as e:
        error_msg = f"Greška pri brisanju memorije: {e}"
        logfire.error(error_msg)
        return error_msg


# --- Inicijalizacija Agenta ---

# Sistemski Prompt
SYSTEM_PROMPT = """
Ti si AI asistent za pronalaženje 'best buy' proizvoda. Slijedi ove korake KORISTEĆI DOSTUPNE ALATE:

1.  **Analiza Upita:** Identificiraj tip proizvoda, budžet (EUR), lokaciju (ako postoji), i specifične kriterije iz korisnikovog zahtjeva.
2.  **Pretraga Webshopova:** Koristi `search_webshops` da nađeš 5-7 relevantnih webshopova.
3.  **Crawl Webshopova:** Za svaki URL iz koraka 2, **pozovi** `crawl_webshop_for_products`. Ovaj alat će (idealno) scrapati proizvode i SPREMITI IH u memoriju (ako je dostupna). Proslijedi mu URL, tip proizvoda, budžet, kriterije.
4.  **Dohvat Proizvoda:** Nakon crawla SVIH webshopova, **pozovi** `retrieve_products_from_memory` da dobiješ listu svih pronađenih proizvoda unutar budžeta. Ako je lista prazna, obavijesti korisnika.
5.  **Pretraga Recenzija:** Za svaki proizvod iz koraka 4 (ili bar top kandidate), **pozovi** `search_product_reviews` da pronađeš 2-3 URL-a recenzija.
6.  **Crawl Recenzija:** Za svaki URL iz koraka 5, **pozovi** `crawl_review_page`. Ovaj alat će (idealno) scrapati recenziju i SPREMITI JE u memoriju (ako je dostupna), povezanu s proizvodom.
7.  **Evaluacija:** Kada su recenzije prikupljene, **pozovi** `evaluate_products` s originalnim budžetom i kriterijima. Ovaj alat će dohvatiti sve iz memorije, analizirati i vratiti konačni `FinalResult`.
8.  **Odgovor Korisniku:** Prikaži `message` i `justification` iz `FinalResult`, te link na `recommended_product.url`. Spomeni i `alternative_products`.
9.  **Čišćenje:** **Nakon** prikaza rezultata, **pozovi** `clear_memory` da pripremiš sustav za sljedeći upit (ako je memorija dostupna).

Budi metodičan. Ako alat vrati grešku ili prazne rezultate, zabilježi to i pokušaj nastaviti ako ima smisla, ili obavijesti korisnika o problemu. Uvijek koristi EUR.
"""

# Kreiranje instance Agenta
agent = Agent(
    llm=llm_model,
    system_prompt=SYSTEM_PROMPT,
    tools=[ # Lista svih definiranih alata
        search_webshops,
        crawl_webshop_for_products,
        search_product_reviews,
        crawl_review_page,
        retrieve_products_from_memory,
        retrieve_reviews_for_product,
        evaluate_products,
        clear_memory,
        # Ovdje dodajte eksplicitne alate za spremanje ako su potrebni
    ],
    mcp_servers=mcp_servers, # Lista konfiguriranih MCP servera
    # debug_mode=True # Korisno za praćenje rada agenta
)


# --- Glavna Funkcija za CLI ---

async def main():
    """Glavna funkcija za pokretanje agenta i interakciju s korisnikom."""
    print("\n--- Best Buy AI Agent (Verzija Groq/Logfire) ---")
    print("Unesite svoj zahtjev (npr. 'Želim best buy bluetooth slušalice za Android u Hrvatskoj, budžet 100 EUR')")
    print("Upišite 'exit' za izlaz.")
    print("-------------------------------------------------")

    # Provjeri jesu li MCP serveri uopće konfigurirani
    if not mcp_servers:
        print("UPOZORENJE: Nijedan MCP server nije konfiguriran. Alati za crawl i memoriju neće raditi.")

    # Pokreni MCP servere ako su definirani i koristi `async with` za upravljanje životnim ciklusom
    async with agent.run_mcp_servers():
        print("MCP serveri (ako su definirani) su pokrenuti.")
        while True:
            try:
                user_input = input("\n[Vi] ")
                if user_input.lower() in ['exit', 'quit', 'bye', 'doviđenja', 'izlaz']:
                    print("Doviđenja!")
                    break
                if not user_input:
                    continue

                # Pokreni agenta s korisnikovim unosom
                logfire.info(f"Pokretanje agenta s unosom: {user_input}")
                span = None
                try:
                    with logfire.span("agent_full_run", user_input=user_input) as span:
                        # Očekujemo da `evaluate_products` alat vrati FinalResult
                        result = await agent.run(user_input, result_type=FinalResult)
                        span.set_attribute("agent_result_type", type(result.data).__name__)

                        # Ispis rezultata
                        if isinstance(result.data, FinalResult):
                            final_data: FinalResult = result.data
                            span.set_attribute("recommendation_found", bool(final_data.recommended_product))
                            print(f"\n[Agent] {final_data.message}")
                            print(f"Obrazloženje: {final_data.justification}")
                            if final_data.recommended_product:
                                print(f"-> Preporučeni proizvod: {final_data.recommended_product.name} ({final_data.recommended_product.price} EUR)")
                                print(f"   Link: {final_data.recommended_product.url}")
                            if final_data.alternative_products:
                                print("\n   Alternativne opcije:")
                                for alt in final_data.alternative_products:
                                    print(f"   - {alt.name} ({alt.price} EUR): {alt.url}")
                        elif isinstance(result.data, str):
                             print(f"\n[Agent] {result.data}")
                             span.set_attribute("agent_result_string", result.data)
                        else:
                            print(f"\n[Agent] Neočekivani odgovor:")
                            print(result.data)
                            span.set_attribute("agent_result_unexpected", str(result.data))
                except Exception as e:
                    if span:
                        span.set_attribute("error", str(e))

                # Pokušaj obrisati memoriju nakon svakog upita
                if mcp_servers and any(server.name == 'memory-server' for server in mcp_servers):
                    try:
                        print("\n[Agent - Održavanje] Čišćenje memorije...")
                        with logfire.span("agent_memory_clear") as clear_span:
                            result = await clear_memory()
                            clear_span.set_attribute("result", result)
                            print(f"[Agent - Održavanje] {result}")
                    except Exception as clear_err:
                        logfire.error(f"Greška pri čišćenju memorije: {clear_err}", exc_info=True)
                        print(f"[Agent - Greška] Nije uspjelo čišćenje memorije: {clear_err}")
                else:
                    print("\n[Agent - Održavanje] Memory server nije konfiguriran, preskačem čišćenje.")


            except Exception as e:
                logfire.error(f"Dogodila se greška u glavnoj petlji: {e}", exc_info=True)
                print(f"\n[Agent - Greška] Dogodila se neočekivana greška: {e}")
                # Možda dodati opciju za resetiranje stanja agenta ako je potrebno

    print("\nAgent je završio s radom.")

# Glavna točka pokretanja skripte
if __name__ == "__main__":
    try:
        with logfire.span("main_session") as main_span:
            try:
                asyncio.run(main())
            except KeyboardInterrupt:
                print("\nIzlaz na zahtjev korisnika.")
                main_span.set_attribute("exit_reason", "keyboard_interrupt")
            except Exception as run_err:
                logfire.error(f"Greška pri izvršavanju: {run_err}", exc_info=True)
                main_span.set_attribute("error", str(run_err))
                print(f"\nGreška pri izvršavanju: {run_err}")
    except Exception as main_err:
        logfire.critical(f"Kritična greška pri pokretanju: {main_err}", exc_info=True)
        print(f"\nKritična greška: {main_err}")
    finally:
        # Osiguraj da se sve zatvori
        for server in mcp_servers:
            try:
                if hasattr(server, 'close'):
                    asyncio.run(server.close())
            except Exception as close_err:
                print(f"Greška pri zatvaranju {server.name}: {close_err}")
        print("\nAgent je završio s radom.")