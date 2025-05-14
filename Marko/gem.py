import asyncio
import os
import json
from typing import List, Optional, Dict, Any, Union
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(override=True)

from pydantic import BaseModel, Field, HttpUrl

# PydanticAI Imports
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.groq import GroqModel
from pydantic_ai.providers.groq import GroqProvider
from pydantic_ai.mcp import MCPServerStdio
from pydantic_ai.tools import Tool
from pydantic_ai.messages import ModelMessage
from pydantic_ai.common_tools.duckduckgo import duckduckgo_search_tool
from pydantic_ai.settings import ModelSettings # Dodano za max_tokens

# Logfire Imports
try:
    import logfire
    LOGFIRE_AVAILABLE = True
except ImportError:
    LOGFIRE_AVAILABLE = False

# --- Environment Variable Loading & API Key Checks ---
groq_api_key = os.getenv("GROQ_API_KEY")
firecrawl_api_key = os.getenv('FIRECRAWL_API_KEY')

if not groq_api_key:
    print("Upozorenje: GROQ_API_KEY nije postavljen. Agent možda neće raditi ispravno.")

# --- Pydantic Models for Data Structuring (s primjerima skraćenih opisa) ---

class SearchCriteria(BaseModel):
    product_type: str = Field(description="Traženi tip proizvoda (npr. bluetooth slušalice)") # Skraćeno
    budget: float = Field(description="Maksimalni budžet") # Skraćeno
    country: Optional[str] = Field(default="Hrvatska", description="Država pretrage") # Skraćeno
    additional_criteria: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Dodatni filteri (npr. {'brand': 'Sony'})") # Skraćeno
    delivery_time_critical: Optional[bool] = Field(default=False, description="Kritično vrijeme dostave?") # Skraćeno

class Webshop(BaseModel):
    name: str = Field(description="Naziv webshopa")
    url: HttpUrl = Field(description="URL webshopa")

class InitialQueryAnalysis(BaseModel):
    """Početna analiza korisnikovog upita.""" # Skraćeno
    extracted_criteria: SearchCriteria = Field(description="Ekstrahirani kriteriji pretrage.") # Skraćeno
    identified_webshops: List[Webshop] = Field(description="Identificirani webshopovi (do 5).") # Skraćeno

class Product(BaseModel):
    id: str = Field(description="ID proizvoda (SKU ili generirani)") # Skraćeno
    name: str = Field(description="Naziv proizvoda")
    price: float = Field(description="Cijena")
    currency: str = Field(default="EUR", description="Valuta")
    url: HttpUrl = Field(description="URL proizvoda")
    webshop_name: str = Field(description="Naziv webshopa gdje je pronađen")
    description: Optional[str] = Field(default=None, description="Opis proizvoda")
    specifications: Optional[Dict[str, Any]] = Field(default=None, description="Specifikacije")

class Review(BaseModel):
    product_id: str = Field(description="ID proizvoda na koji se odnosi recenzija")
    review_text: str = Field(description="Tekst recenzije")
    rating: Optional[float] = Field(default=None, description="Ocjena (1-5), ako postoji")
    source_url: Optional[HttpUrl] = Field(default=None, description="URL izvora recenzije")

class BestBuyResult(BaseModel):
    product_name: str
    price: float
    currency: str
    webshop_name: str
    product_url: HttpUrl
    justification: str = Field(description="Obrazloženje odabira") # Skraćeno

class FailedSearch(BaseModel):
    reason: str = Field(description="Razlog neuspjele pretrage") # Skraćeno

# --- MCP Server Configuration ---
mcp_servers_config = [
    MCPServerStdio('npx', ['-y', "@modelcontextprotocol/server-memory"]),
    MCPServerStdio('npx', ["-y", "firecrawl-mcp"], {
        "FIRECRAWL_API_KEY": firecrawl_api_key or ""
    }),
]

# --- LLM Model Configuration ---
llm_model = GroqModel(
    'llama3-70b-8192',
    provider=GroqProvider(api_key=groq_api_key)
)

# --- Logfire Configuration ---
if LOGFIRE_AVAILABLE:
    try:
        logfire.configure(
            pydantic_ai_collect_raw_inputs_outputs=True
        )
    except Exception as e:
        print(f"Greška pri konfiguraciji Logfire: {e}")
        LOGFIRE_AVAILABLE = False
else:
    print("Logfire biblioteka nije dostupna. Logiranje neće biti aktivno.")

# --- Main Agent Definition ---
class BestBuyAgentDependencies(BaseModel):
    pass

available_tools = [duckduckgo_search_tool()] # Samo DuckDuckGo za početak, ostali se dodaju preko dekoratora

best_buy_agent = Agent(
    model=llm_model,
    deps_type=BestBuyAgentDependencies,
    tools=available_tools,
    mcp_servers=mcp_servers_config,
    system_prompt=( # SKRAĆENI SISTEMSKI PROMPT
        "Ti si AI asistent za najbolju kupovinu. Pomozi korisniku analizirati upit, pronaći webshopove i proizvode, te evaluirati recenzije. Koristi dostupne alate efikasno."
    ),
)

if LOGFIRE_AVAILABLE:
    try:
        best_buy_agent.instrument()
    except Exception as e:
        print(f"Greška pri instrumentaciji agenta s Logfire: {e}")

# --- Tool Definitions (Custom) ---
def get_mcp_client_by_identifier(ctx: RunContext, identifier: str) -> Optional[Any]:
    if ctx.mcp_clients and identifier in ctx.mcp_clients:
        return ctx.mcp_clients[identifier]
    if ctx.mcp_clients:
        for client_key, client_wrapper in ctx.mcp_clients.items():
            server_instance_attr_names = ['_server_instance', 'server'] 
            server_instance = None
            for attr_name in server_instance_attr_names:
                if hasattr(client_wrapper, attr_name):
                    server_instance = getattr(client_wrapper, attr_name)
                    break
            if server_instance and hasattr(server_instance, 'args') and isinstance(server_instance.args, list):
                if any(identifier in arg_part for arg_part in server_instance.args):
                    return client_wrapper
    print(f"Upozorenje: MCP klijent za identifikator '{identifier}' nije pronađen.")
    print(f"Dostupni ključevi MCP klijenata: {list(ctx.mcp_clients.keys()) if ctx.mcp_clients else 'Nema dostupnih MCP klijenata.'}")
    return None

@best_buy_agent.tool
async def crawl_webshop_for_products(
    ctx: RunContext[BestBuyAgentDependencies],
    webshop_url: HttpUrl,
    webshop_name: str,
    search_criteria: SearchCriteria # Prima SearchCriteria kao objekt
) -> List[Product]:
    """
    Pregledava specificirani webshop (putem Firecrawl MCP servera) kako bi pronašao proizvode
    koji odgovaraju zadanim kriterijima.
    """
    print(f"[Tool: crawl_webshop_for_products] Crawlam {webshop_name} ({webshop_url}) za proizvode...")
    firecrawl_client = get_mcp_client_by_identifier(ctx, 'firecrawl-mcp')
    memory_client = get_mcp_client_by_identifier(ctx, '@modelcontextprotocol/server-memory')
    products_found = []

    if not firecrawl_client:
        print("Upozorenje: Firecrawl MCP klijent ('firecrawl-mcp') nije dostupan.")
        return []
    try:
        target_scrape_url = f"{webshop_url}" # LLM treba formirati bolji URL za pretragu unutar shopa
        print(f"  Firecrawl poziv za URL (simulacija): {target_scrape_url}")
        # Stvarni poziv: response_data = await firecrawl_client.call_method('scrape', url=str(target_scrape_url), ...)
        await asyncio.sleep(1)
        sim_products_data = []
        if "example-techshop-cro.com" in str(webshop_url):
            sim_products_data = [
                {"id": f"{webshop_name}_s1", "name": "SuperZvuk Pro", "price": 99.99, "url": f"{str(webshop_url)}/product/superzvuk_pro", "description": "Profesionalne BT slušalice.", "specifications": {"compatibility": "android, ios", "type": "over-ear"}},
                {"id": f"{webshop_name}_s2", "name": "AudioBliss Lite", "price": 49.50, "url": f"{str(webshop_url)}/product/audiobliss_lite", "description": "Lagane BT slušalice za svaki dan.", "specifications": {"compatibility": "android", "type": "in-ear"}},
            ]
        for p_data in sim_products_data:
            passes_additional_criteria = True
            if search_criteria.additional_criteria and p_data.get("specifications"):
                for key, value in search_criteria.additional_criteria.items():
                    spec_value = p_data["specifications"].get(key)
                    if spec_value and value.lower() not in str(spec_value).lower():
                        passes_additional_criteria = False
                        break
            if p_data["price"] <= search_criteria.budget and passes_additional_criteria:
                product = Product(
                    id=p_data["id"], name=p_data["name"], price=p_data["price"],
                    url=HttpUrl(p_data["url"]), webshop_name=webshop_name, # Osiguraj HttpUrl
                    description=p_data.get("description"), specifications=p_data.get("specifications")
                )
                products_found.append(product)
                print(f"    Pronađen proizvod: {product.name} ({product.price} EUR)")
                if memory_client:
                    try:
                        # await memory_client.call_method('upsert_entity', ...)
                        print(f"    Proizvod '{product.name}' (simulirano) spremljen u memoriju.")
                    except Exception as e: print(f"Greška pri spremanju u memoriju: {e}")
    except Exception as e: print(f"Greška pri crawl-anju {webshop_url}: {e}")
    return products_found

@best_buy_agent.tool
async def find_product_reviews(ctx: RunContext[BestBuyAgentDependencies], product_name: str, product_id: str) -> List[Review]:
    print(f"[Tool: find_product_reviews] Tražim recenzije za '{product_name}' (ID: {product_id})...")
    firecrawl_client = get_mcp_client_by_identifier(ctx, 'firecrawl-mcp')
    memory_client = get_mcp_client_by_identifier(ctx, '@modelcontextprotocol/server-memory')
    reviews_found = []
    simulated_review_urls_str = []
    if product_id.endswith("_s1"): simulated_review_urls_str = ["https://example-reviewsite.com/superzvuk_pro_rec1", "https://example-blog.com/audio/superzvuk_pro_test"]
    elif product_id.endswith("_s2"): simulated_review_urls_str = ["https://example-reviewsite.com/audiobliss_lite_rec"]

    if not firecrawl_client and simulated_review_urls_str:
        print("Upozorenje: Firecrawl MCP klijent nije dostupan.")
        for url_str in simulated_review_urls_str:
            reviews_found.append(Review(product_id=product_id, review_text=f"Recenzija na {url_str} (sadržaj nije dohvaćen)", source_url=HttpUrl(url_str)))
        return reviews_found
    if not simulated_review_urls_str: return []

    for review_url_str in simulated_review_urls_str:
        review_url = HttpUrl(review_url_str)
        print(f"  Pokušavam crawlati recenziju s URL-a: {review_url}")
        try:
            # response_data = await firecrawl_client.call_method('scrape', url=str(review_url), ...)
            await asyncio.sleep(0.5)
            review_text_content = f"Simulirani sadržaj recenzije s {review_url} za {product_name}. Odličan!"
            rating_extracted = None
            if "superzvuk_pro_rec1" in str(review_url): rating_extracted = 5.0
            elif "superzvuk_pro_test" in str(review_url): rating_extracted = 4.5
            elif "audiobliss_lite_rec" in str(review_url): rating_extracted = 3.5
            review = Review(product_id=product_id, review_text=review_text_content, rating=rating_extracted, source_url=review_url)
            reviews_found.append(review)
            print(f"    Pronađena recenzija: {review.review_text[:30]}...")
            if memory_client:
                try:
                    # await memory_client.call_method('upsert_entity', ...)
                    print(f"    Recenzija za '{product_name}' (simulirano) spremljena.")
                except Exception as e: print(f"Greška pri spremanju recenzije: {e}")
        except Exception as e: print(f"Greška pri crawl-anju recenzije {review_url}: {e}")
    return reviews_found

@best_buy_agent.tool
async def process_reviews_and_decide(
    ctx: RunContext[BestBuyAgentDependencies],
    products: List[Product],
    all_reviews: Dict[str, List[Review]],
    search_criteria: SearchCriteria
) -> Union[BestBuyResult, FailedSearch]:
    print(f"[Tool: process_reviews_and_decide] Analiziram {len(products)} proizvoda...")
    if not products: return FailedSearch(reason="Nema proizvoda za finalnu evaluaciju.")
    best_candidate: Optional[Product] = None
    best_score = -float('inf') # Inicijalizacija na vrlo malu vrijednost
    justification_for_best = "Nije pronađen dovoljno dobar kandidat."

    for product in products:
        if product.price > search_criteria.budget: continue
        current_score = 0.0
        price_score = (search_criteria.budget - product.price) / search_criteria.budget if search_criteria.budget > 0 else 0
        current_score += price_score * 0.4
        product_reviews_list = all_reviews.get(product.id, [])
        avg_rating = 0.0
        num_valid_reviews = 0
        if product_reviews_list:
            for r in product_reviews_list:
                if r.rating is not None and 1.0 <= r.rating <= 5.0:
                    avg_rating += r.rating
                    num_valid_reviews += 1
            if num_valid_reviews > 0:
                avg_rating /= num_valid_reviews
                current_score += (avg_rating / 5.0) * 0.6
            elif any(r.review_text for r in product_reviews_list): current_score += 0.05 # Manji bonus
        else: current_score -= 0.05 # Manji penal

        if search_criteria.additional_criteria and product.specifications:
            match_count = 0
            total_criteria = len(search_criteria.additional_criteria)
            if total_criteria > 0:
                for key, value in search_criteria.additional_criteria.items():
                    spec_value = product.specifications.get(key)
                    if spec_value and value.lower() in str(spec_value).lower(): match_count += 1
                current_score += (match_count / total_criteria) * 0.2
        
        print(f"  Proizvod: {product.name}, Cijena: {product.price}, Prosj.Ocjena: {avg_rating if num_valid_reviews > 0 else 'N/A'}, Score: {current_score:.2f}")
        if current_score > best_score:
            best_score = current_score
            best_candidate = product
            justification_for_best = f"Proizvod '{product.name}' nudi dobar omjer cijene ({product.price} EUR) i recenzija (prosjek: {avg_rating if num_valid_reviews > 0 else 'N/A'})."
            if num_valid_reviews == 0 and any(r.review_text for r in product_reviews_list): justification_for_best += " Postoje tekstualne recenzije."
            elif num_valid_reviews == 0: justification_for_best += " Nema dostupnih recenzija."

    if best_candidate and best_score > 0.05: # Malo spušten prag za testiranje
        return BestBuyResult(
            product_name=best_candidate.name, price=best_candidate.price, currency=best_candidate.currency,
            webshop_name=best_candidate.webshop_name, product_url=best_candidate.url,
            justification=justification_for_best
        )
    return FailedSearch(reason=f"Nakon analize, nijedan proizvod nije zadovoljio kriterije s dovoljno visokom ocjenom. Najbolji kandidat je imao score {best_score:.2f}. {justification_for_best}")

# --- Glavni CLI tok ---
async def best_buy_workflow(user_query: str):
    print(f"\nPokrećem BestBuy workflow za upit: '{user_query}'")
    history: List[ModelMessage] = []
    try:
        print("\n--- Korak 1: Analiza upita i identifikacija webshopova ---")
        analysis_prompt = ( # SKRAĆENI PROMPT ZA PRVI KORAK
            f"Korisnički upit: '{user_query}'.\n"
            f"Zadaci:\n"
            f"1. Iz upita ekstrahiraj kriterije (tip proizvoda, budžet, država, dodatno) u 'SearchCriteria' format.\n"
            f"2. Koristeći 'duckduckgo_search_tool', pronađi do 5 relevantnih webshopova u navedenoj državi za taj tip proizvoda.\n"
            f"3. Vrati konačni rezultat kao 'InitialQueryAnalysis' objekt."
        )
        
        run_initial_analysis = await best_buy_agent.run(
            analysis_prompt,
            output_type=InitialQueryAnalysis,
            message_history=history,
            model_settings=ModelSettings(max_tokens=2000) # Ograničenje tokena za odgovor LLM-a (ne za cijeli kontekst)
        )
        history.extend(run_initial_analysis.new_messages())

        if not isinstance(run_initial_analysis.output, InitialQueryAnalysis):
            print("Nisam uspio analizirati upit. Agentov odgovor:")
            print(run_initial_analysis.output if run_initial_analysis.output else "Nema odgovora.")
            return

        initial_analysis: InitialQueryAnalysis = run_initial_analysis.output
        search_criteria = initial_analysis.extracted_criteria
        webshops = initial_analysis.identified_webshops
        print(f"\nEkstrahirani kriteriji: {search_criteria.model_dump_json(indent=2)}")
        if not webshops:
            print("Nije identificiran nijedan webshop.")
            return
        print(f"\nIdentificirani webshopovi ({len(webshops)}):")
        for ws in webshops: print(f"- {ws.name} ({ws.url})")

        print("\n--- Korak 2: Crawlanje webshopova ---")
        all_found_products: List[Product] = []
        for webshop in webshops:
            product_crawl_prompt = (
                f"Pregledaj webshop '{webshop.name}' ({webshop.url}) alatom 'crawl_webshop_for_products'. "
                f"Argumenti za alat: webshop_url='{str(webshop.url)}', webshop_name='{webshop.name}', "
                f"search_criteria={search_criteria.model_dump_json(exclude_none=True)}. Vrati listu proizvoda."
            )
            run_result_products = await best_buy_agent.run(product_crawl_prompt, message_history=history, model_settings=ModelSettings(max_tokens=1500))
            history.extend(run_result_products.new_messages())
            products_from_shop: List[Product] = []
            if run_result_products.tool_calls:
                for tc in run_result_products.tool_calls:
                    if tc.tool_name == "crawl_webshop_for_products" and tc.result:
                        if isinstance(tc.result, list) and all(isinstance(item, Product) for item in tc.result):
                           products_from_shop.extend(tc.result)
                        else:
                            try: parsed_list = json.loads(str(tc.result)); products_from_shop.extend([Product(**item) for item in parsed_list])
                            except Exception as e: print(f"Greška parsiranja crawl rezultata za {webshop.name}: {e}. Rezultat: {tc.result}")
            if products_from_shop:
                all_found_products.extend(products_from_shop)
                print(f"  Na {webshop.name} pronađeno: {len(products_from_shop)} proizvoda.")
        
        if not all_found_products: print("\nNije pronađen nijedan proizvod."); return
        print(f"\nUkupno pronađeno proizvoda ({len(all_found_products)}):")
        for prod in all_found_products: print(f"- {prod.name} ({prod.price} EUR) na {prod.webshop_name}")

        print("\n--- Korak 3: Traženje recenzija ---")
        all_product_reviews: Dict[str, List[Review]] = {}
        for product in all_found_products:
            review_search_prompt = (
                f"Alatom 'find_product_reviews' pronađi recenzije za '{product.name}' (ID: {product.id}). "
                f"Argumenti: product_name='{product.name}', product_id='{product.id}'. Vrati listu recenzija."
            )
            run_result_reviews = await best_buy_agent.run(review_search_prompt, message_history=history, model_settings=ModelSettings(max_tokens=1500))
            history.extend(run_result_reviews.new_messages())
            reviews_for_product: List[Review] = []
            if run_result_reviews.tool_calls:
                for tc in run_result_reviews.tool_calls:
                    if tc.tool_name == "find_product_reviews" and tc.result:
                        if isinstance(tc.result, list) and all(isinstance(item, Review) for item in tc.result):
                            reviews_for_product.extend(tc.result)
                        else:
                            try: parsed_list = json.loads(str(tc.result)); reviews_for_product.extend([Review(**item) for item in parsed_list])
                            except Exception as e: print(f"Greška parsiranja review rezultata za {product.name}: {e}. Rezultat: {tc.result}")
            all_product_reviews[product.id] = reviews_for_product
            if reviews_for_product: print(f"  Za {product.name} pronađeno: {len(reviews_for_product)} recenzija.")

        print("\n--- Korak 4/5: Finalna analiza i odluka ---")
        # Priprema podataka za alat 'process_reviews_and_decide'
        # Zbog potencijalne duljine, šaljemo samo ID-eve i kratke opise, a alat dohvaća detalje ako treba
        # Ili, ako LLM može podnijeti, šaljemo sve. Za sada šaljemo sve.
        products_json_str = json.dumps([p.model_dump(exclude_none=True, exclude_defaults=True) for p in all_found_products])
        reviews_json_str = json.dumps({pid: [r.model_dump(exclude_none=True, exclude_defaults=True) for r in reviews] for pid, reviews in all_product_reviews.items()})
        criteria_json_str = search_criteria.model_dump_json(exclude_none=True)

        # Provjera duljine prije slanja LLM-u
        # Ovo je gruba provjera, stvarni token count je bitan
        if len(products_json_str) + len(reviews_json_str) + len(criteria_json_str) > 7000 : # Ostavljamo nešto za prompt i output
            print("Upozorenje: Podaci za finalnu odluku su vrlo dugački, LLM može imati problema.")
            # Ovdje bi mogla ići logika za sažimanje ili slanje samo najbitnijih dijelova

        final_decision_prompt = (
            f"Koristeći alat 'process_reviews_and_decide', odaberi najbolji proizvod. "
            f"Argumenti za alat:\n"
            f"products={products_json_str}\n"
            f"all_reviews={reviews_json_str}\n"
            f"search_criteria={criteria_json_str}\n"
            f"Vrati rezultat kao 'BestBuyResult' ili 'FailedSearch'."
        )
        run_result_decision = await best_buy_agent.run(
            final_decision_prompt, 
            output_type=Union[BestBuyResult, FailedSearch], 
            message_history=history,
            model_settings=ModelSettings(max_tokens=1500) # Max tokena za odgovor
        )
        final_decision = run_result_decision.output # Ne treba history.extend ovdje, ovo je zadnji korak

        if isinstance(final_decision, BestBuyResult):
            print("\n--- Najbolja Kupovina ---")
            print(f"Proizvod: {final_decision.product_name}")
            print(f"Cijena: {final_decision.price} {final_decision.currency}")
            print(f"Webshop: {final_decision.webshop_name}")
            print(f"Link: {final_decision.product_url}")
            print(f"Obrazloženje: {final_decision.justification}")
        elif isinstance(final_decision, FailedSearch):
            print("\n--- Pretraga Nije Uspjela ---"); print(f"Razlog: {final_decision.reason}")
        else: print("\n--- Neočekivani Odgovor Agenta ---"); print(final_decision)
        print("\n(Simulacija) Memorija bi se sada obrisala.")
    except Exception as e:
        print(f"\nDošlo je do greške tijekom BestBuy workflowa: {e}")
        import traceback
        traceback.print_exc()

async def main_cli():
    print("Dobrodošli u BestBuy AI Agent!")
    print("Unesite 'exit' za izlaz.")
    print("Napomena: API varijable trebaju biti postavljene.")
    try:
        async with best_buy_agent.run_mcp_servers():
            print("Info: MCP serveri (trebali bi biti) pokrenuti.")
            while True:
                user_input = input("\nŠto želite kupiti? (npr. 'best buy bluetooth slušalice za android u hrvatskoj, imam 100 EUR'): \n> ")
                if user_input.lower() == 'exit': break
                if not user_input.strip(): continue
                await best_buy_workflow(user_input)
    except Exception as e:
        print(f"Kritična greška s MCP serverima ili glavnom petljom: {e}")
        import traceback; traceback.print_exc()
    finally: print("Info: Završavam rad (MCP serveri bi se trebali zaustaviti).")
    print("Hvala. Doviđenja!")

if __name__ == "__main__":
    if groq_api_key:
        asyncio.run(main_cli())
    else:
        print("GREŠKA: GROQ_API_KEY nije postavljen. Provjerite .env datoteku.")