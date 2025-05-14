import asyncio
import os
import json
from typing import List, Optional, Dict, Any, Union

from pydantic import BaseModel, Field, HttpUrl

# PydanticAI Imports
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.groq import GroqModel
from pydantic_ai.providers.groq import GroqProvider
from pydantic_ai.mcp import MCPServerStdio
from pydantic_ai.tools import Tool
from pydantic_ai.messages import ModelMessage # Potrebno za povijest poruka

# Logfire Imports (ako se koristi zasebno, inače PydanticAI ima svoju integraciju)
try:
    import logfire
    LOGFIRE_AVAILABLE = True
except ImportError:
    LOGFIRE_AVAILABLE = False

# --- Environment Variable Loading & API Key Checks ---
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
FIRECRAWL_API_KEY = os.getenv('FIRECRAWL_API_KEY')

if not GROQ_API_KEY:
    print("Upozorenje: GROQ_API_KEY nije postavljen. Agent možda neće raditi ispravno.")
if not FIRECRAWL_API_KEY:
    print("Upozorenje: FIRECRAWL_API_KEY nije postavljen. Web crawling funkcionalnost će biti ograničena.")

# --- Pydantic Models for Data Structuring ---

class SearchCriteria(BaseModel):
    product_type: str = Field(description="Vrsta proizvoda za pretragu (npr. 'bluetooth slušalice')")
    budget: float = Field(description="Maksimalni iznos novca za potrošiti")
    country: Optional[str] = Field(default="Hrvatska", description="Država u kojoj se traži proizvod")
    additional_criteria: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Dodatni kriteriji (npr. {'brand': 'Sony', 'color': 'black'})")
    delivery_time_critical: Optional[bool] = Field(default=False, description="Je li vrijeme dostave kritično")

class Webshop(BaseModel):
    name: str
    url: HttpUrl
    product_category_path: Optional[str] = Field(default=None, description="Putanja do kategorije proizvoda na webshopu")

class Product(BaseModel):
    id: str = Field(description="Jedinstveni identifikator proizvoda")
    name: str
    price: float
    currency: str = "EUR"
    url: HttpUrl
    webshop_name: str
    description: Optional[str] = None
    specifications: Optional[Dict[str, Any]] = None
    reviews_summary: Optional[str] = None # Sažetak review-a ili link na njih

class Review(BaseModel):
    product_id: str
    review_text: str
    rating: Optional[float] = None # Ocjena od 1-5
    source_url: Optional[HttpUrl] = None

class BestBuyResult(BaseModel):
    product_name: str
    price: float
    currency: str
    webshop_name: str
    product_url: HttpUrl
    justification: str = Field(description="Obrazloženje zašto je ovaj proizvod najbolji izbor")

class FailedSearch(BaseModel):
    reason: str = Field(description="Razlog zašto nije pronađen odgovarajući proizvod")

# --- MCP Server Configuration ---
# Prema uputama korisnika
mcp_servers_config = [
    MCPServerStdio('npx', ['-y', "@modelcontextprotocol/server-memory"], name="memory_server"),
    MCPServerStdio('npx', ["-y", "firecrawl-mcp"], {
        "FIRECRAWL_API_KEY": FIRECRAWL_API_KEY or ""
    }, name="firecrawl_server"),
]

# --- LLM Model Configuration ---
# Prema uputama korisnika
llm_model = GroqModel(
    'llama3-70b-8192', # Korištenje Llama3 70B modela umjesto Maverick-a koji je deprecated
    provider=GroqProvider(api_key=GROQ_API_KEY)
)

# --- Logfire Configuration ---
if LOGFIRE_AVAILABLE:
    try:
        logfire.configure(
            pydantic_ai_collect_raw_inputs_outputs=True # Za detaljniji log PydanticAI
        )
        # Agent.instrument_all() # Instrumentacija svih agenata
        # Ako se koristi PydanticAI instrumentacija, ovo se može pozvati na instanci agenta
    except Exception as e:
        print(f"Greška pri konfiguraciji Logfire: {e}")
        LOGFIRE_AVAILABLE = False
else:
    print("Logfire biblioteka nije dostupna. Logiranje neće biti aktivno.")


# --- Main Agent Definition ---
# Za sada, jedan glavni agent koji koristi alate za različite faze.
# U naprednijoj verziji, ovo bi se moglo podijeliti na više specijaliziranih agenata
# koji međusobno komuniciraju (npr., korištenjem pydantic_graph).

class BestBuyAgentDependencies(BaseModel):
    """ Ovdje se mogu definirati ovisnosti ako su potrebne alatima, npr. HTTP klijenti """
    pass # Za sada prazno


best_buy_agent = Agent(
    model=llm_model,
    # output_type=Union[BestBuyResult, FailedSearch], # Type hint za Pyright/Mypy
    # Za PydanticAI, output_type se često specificira u run metodi ili alatima
    deps_type=BestBuyAgentDependencies,
    mcp_servers=mcp_servers_config,
    system_prompt=(
        "Ti si AI agent za pronalaženje najbolje kupovine. Tvoj zadatak je pomoći korisniku pronaći "
        "najbolji proizvod unutar zadanog budžeta i kriterija. Koristi dostupne alate za pretragu webshopova, "
        "pronalaženje proizvoda, analizu recenzija i donošenje odluke. Budi temeljit i precizan."
    ),
    # instrument=LOGFIRE_AVAILABLE # Instrumentiraj agenta ako je Logfire dostupan
)
if LOGFIRE_AVAILABLE:
    try:
        best_buy_agent.instrument()
    except Exception as e:
        print(f"Greška pri instrumentaciji agenta s Logfire: {e}")


# --- Tool Definitions ---

# Konceptualni alati koje će agent koristiti. Implementacija bi pozivala MCP servere.

@best_buy_agent.tool
async def find_webshops(ctx: RunContext[BestBuyAgentDependencies], product_type: str, country: str) -> List[Webshop]:
    """
    Pretražuje web kako bi pronašao relevantne webshopove za dani tip proizvoda i državu.
    Vraća listu od maksimalno 10 webshopova.
    """
    # U stvarnoj implementaciji, ovaj alat bi koristio Google Search ili sličan opći pretraživač.
    # Ovdje simuliramo rezultat.
    # Za potrebe demonstracije, koristit ćemo Google Search alat ako je dostupan
    # PydanticAI nema ugrađen Google Search alat direktno, ali LLM može biti instruiran da ga koristi
    # ili bi se morao dodati kao custom tool koji poziva vanjski API.
    # Za ovaj primjer, vraćamo fiksnu listu.
    print(f"[Tool: find_webshops] Tražim webshopove za '{product_type}' u '{country}'...")
    await asyncio.sleep(1) # Simulacija mrežnog poziva

    # Primjer kako bi se koristio MCP memory server za dohvat ili spremanje
    # memory_client = ctx.mcp_client('memory_server')
    # if memory_client:
    #     try:
    #         # Primjer: dohvati spremljene webshopove za ovaj upit
    #         # shops = await memory_client.query_entities(...)
    #         pass
    #     except Exception as e:
    #         print(f"Greška pri radu s memory serverom u find_webshops: {e}")


    # Vraćamo hardkodiranu listu za primjer
    if "slušalice" in product_type.lower():
        return [
            Webshop(name="TechShopCRO", url="[https://example-techshop-cro.com](https://example-techshop-cro.com)", product_category_path="/audio/slusalice"),
            Webshop(name="ZvukPlus", url="[https://example-zvukplus.hr](https://example-zvukplus.hr)", product_category_path="/slusalice"),
            Webshop(name="MobilMedia", url="[https://example-mobilmedia.com](https://example-mobilmedia.com)", product_category_path="/accessories/headphones"),
        ]
    return []

@best_buy_agent.tool
async def crawl_webshop_for_products(
    ctx: RunContext[BestBuyAgentDependencies],
    webshop_url: HttpUrl,
    search_criteria: SearchCriteria
) -> List[Product]:
    """
    Pregledava specificirani webshop (putem Firecrawl MCP servera) kako bi pronašao proizvode
    koji odgovaraju zadanim kriterijima (tip proizvoda, budžet, dodatni filteri).
    Sprema pronađene proizvode u memoriju (putem Memory MCP servera).
    """
    print(f"[Tool: crawl_webshop_for_products] Crawlam {webshop_url} za proizvode prema kriterijima...")

    firecrawl_client = ctx.mcp_client('firecrawl_server')
    memory_client = ctx.mcp_client('memory_server')
    products_found = []

    if not firecrawl_client:
        print("Upozorenje: Firecrawl MCP klijent nije dostupan. Ne mogu crawlati webshop.")
        return []

    try:
        # Primjer poziva Firecrawl scrape (stvarni parametri ovise o implementaciji Firecrawl MCP servera)
        # Dokumentacija za Firecrawl: [https://github.comm/mendableai/firecrawl-mcp-server](https://github.comm/mendableai/firecrawl-mcp-server)
        # URL za scrape bi trebao biti formiran na temelju webshop_url i search_criteria.product_type
        # npr. webshop_url + (webshop.product_category_path or f"/search?q={search_criteria.product_type}")
        target_scrape_url = f"{webshop_url}" # Pojednostavljeno
        if "example-techshop-cro.com" in str(webshop_url) and "slušalice" in search_criteria.product_type:
             target_scrape_url = f"{webshop_url}/audio/slusalice?budget_max={search_criteria.budget}"


        print(f"  Firecrawl poziv za URL: {target_scrape_url}")
        # Pretpostavljamo da firecrawl alat vraća strukturirane podatke o proizvodima
        # response = await firecrawl_client.scrape(url=target_scrape_url, params={'crawlerSettings': {'maxDepth': 1, 'includeFileTypes': ['html']}})
        # Ovdje bi išla logika za parsiranje `response.data` (npr. ako je Markdown ili JSON)
        # i kreiranje Product objekata.

        # Simulacija rezultata crawl-a
        await asyncio.sleep(2) # Simulacija mrežnog poziva i obrade
        if "example-techshop-cro.com" in str(webshop_url) and "slušalice" in search_criteria.product_type:
            sim_products_data = [
                {"id": "tech_s1", "name": "SuperZvuk Pro", "price": 99.99, "url": f"{webshop_url}/product/superzvuk_pro", "description": "Profesionalne BT slušalice."},
                {"id": "tech_s2", "name": "AudioBliss Lite", "price": 49.50, "url": f"{webshop_url}/product/audiobliss_lite", "description": "Lagane BT slušalice za svaki dan."},
                {"id": "tech_s3", "name": "GamerHear Max", "price": 120.00, "url": f"{webshop_url}/product/gamerhear_max", "description": "Gaming BT slušalice."}, # Preko budžeta
            ]
            for p_data in sim_products_data:
                if p_data["price"] <= search_criteria.budget:
                    product = Product(
                        id=p_data["id"],
                        name=p_data["name"],
                        price=p_data["price"],
                        url=p_data["url"],
                        webshop_name=str(webshop_url), # Ili naziv webshopa
                        description=p_data.get("description")
                    )
                    products_found.append(product)
                    print(f"    Pronađen proizvod: {product.name} ({product.price} EUR)")
                    if memory_client:
                        try:
                            # Spremanje entiteta (proizvoda)
                            # Stvarna struktura za MCP memory ovisi o specifikaciji servera
                            await memory_client.upsert_entity(
                                entity_type="product",
                                entity_id=product.id,
                                data=product.model_dump()
                            )
                            # Povezivanje proizvoda s webshopom (ako modeliramo kao graf znanja)
                            # await memory_client.create_relation(
                            #     source_entity_type="webshop",
                            #     source_entity_id=webshop_url, # ili ID webshopa
                            #     target_entity_type="product",
                            #     target_entity_id=product.id,
                            #     relation_type="sells_product"
                            # )
                            print(f"    Proizvod '{product.name}' spremljen u memoriju.")
                        except Exception as e:
                            print(f"Greška pri spremanju proizvoda u memoriju: {e}")

    except Exception as e:
        print(f"Greška pri crawl-anju webshopa {webshop_url}: {e}")

    return products_found

@best_buy_agent.tool
async def find_product_reviews(ctx: RunContext[BestBuyAgentDependencies], product_name: str, product_id: str) -> List[Review]:
    """
    Pretražuje web za recenzije (reviews) o specificiranom proizvodu.
    Sprema pronađene recenzije u memoriju i povezuje ih s proizvodom.
    """
    print(f"[Tool: find_product_reviews] Tražim recenzije za '{product_name}' (ID: {product_id})...")
    firecrawl_client = ctx.mcp_client('firecrawl_server')
    memory_client = ctx.mcp_client('memory_server')
    reviews_found = []

    if not firecrawl_client:
        print("Upozorenje: Firecrawl MCP klijent nije dostupan. Ne mogu tražiti recenzije.")
        return []

    try:
        # Primjer poziva Firecrawl search (ako podržava općenitu pretragu, ili bi se koristio Google Search)
        # search_query = f"recenzije {product_name}"
        # response = await firecrawl_client.search(query=search_query)
        # Ovdje bi išla logika za parsiranje `response.data` i zatim crawl pojedinačnih linkova za recenzije.

        # Simulacija rezultata pretrage recenzija
        await asyncio.sleep(1)
        sim_reviews_data = []
        if product_id == "tech_s1": # SuperZvuk Pro
            sim_reviews_data = [
                {"text": "Odlične slušalice, zvuk je kristalno čist!", "rating": 5.0, "url": "[https://example-reviewsite.com/superzvuk_pro_rec1](https://example-reviewsite.com/superzvuk_pro_rec1)"},
                {"text": "Baterija traje dugo, preporuka.", "rating": 4.5, "url": "[https://example-blog.com/audio/superzvuk_pro_test](https://example-blog.com/audio/superzvuk_pro_test)"},
            ]
        elif product_id == "tech_s2": # AudioBliss Lite
             sim_reviews_data = [
                {"text": "Dobre za tu cijenu, ali bas bi mogao biti jači.", "rating": 3.5, "url": "[https://example-reviewsite.com/audiobliss_lite_rec](https://example-reviewsite.com/audiobliss_lite_rec)"},
            ]

        for r_data in sim_reviews_data:
            review = Review(
                product_id=product_id,
                review_text=r_data["text"],
                rating=r_data.get("rating"),
                source_url=r_data.get("url")
            )
            reviews_found.append(review)
            print(f"    Pronađena recenzija: {review.review_text[:50]}...")
            if memory_client:
                try:
                    # Spremanje entiteta (recenzije)
                    # ID recenzije bi se mogao generirati (npr. hash teksta ili URL-a)
                    review_id = f"review_{product_id}_{hash(review.review_text)}"
                    await memory_client.upsert_entity(
                        entity_type="review",
                        entity_id=review_id, # Generirani ID
                        data=review.model_dump()
                    )
                    # Povezivanje recenzije s proizvodom
                    # await memory_client.create_relation(
                    #     source_entity_type="product",
                    #     source_entity_id=product_id,
                    #     target_entity_type="review",
                    #     target_entity_id=review_id,
                    #     relation_type="has_review"
                    # )
                    print(f"    Recenzija za '{product_name}' spremljena u memoriju.")
                except Exception as e:
                    print(f"Greška pri spremanju recenzije u memoriju: {e}")

    except Exception as e:
        print(f"Greška pri traženju recenzija za {product_name}: {e}")

    return reviews_found


@best_buy_agent.tool
async def process_reviews_and_decide(
    ctx: RunContext[BestBuyAgentDependencies],
    products: List[Product],
    all_reviews: Dict[str, List[Review]], # Ključ je product_id
    search_criteria: SearchCriteria
) -> Union[BestBuyResult, FailedSearch]:
    """
    Analizira sve prikupljene proizvode i njihove recenzije kako bi odabrao najbolji proizvod
    prema zadanim kriterijima i budžetu.
    Koristi LLM za "razumijevanje" recenzija i donošenje odluke.
    """
    print(f"[Tool: process_reviews_and_decide] Analiziram {len(products)} proizvoda...")
    if not products:
        return FailedSearch(reason="Nije pronađen nijedan proizvod koji odgovara početnim kriterijima.")

    # Ovdje bi išla kompleksnija logika evaluacije.
    # Za sada, koristimo LLM da pregleda podatke i da prijedlog.
    # Pripremamo prompt za LLM:

    prompt_details = f"Korisnik traži: {search_criteria.product_type} s budžetom do {search_criteria.budget} EUR.\n"
    if search_criteria.additional_criteria:
        prompt_details += f"Dodatni kriteriji: {json.dumps(search_criteria.additional_criteria)}\n"
    prompt_details += "Pronađeni su sljedeći proizvodi i njihove recenzije:\n\n"

    for product in products:
        prompt_details += f"Proizvod: {product.name}\n"
        prompt_details += f"Cijena: {product.price} {product.currency}\n"
        prompt_details += f"Webshop: {product.webshop_name}\n"
        prompt_details += f"URL: {product.url}\n"
        if product.description:
            prompt_details += f"Opis: {product.description}\n"

        product_reviews = all_reviews.get(product.id, [])
        if product_reviews:
            prompt_details += "Recenzije:\n"
            for review in product_reviews:
                prompt_details += f"- Ocjena: {review.rating if review.rating else 'N/A'}. Tekst: {review.review_text}\n"
        else:
            prompt_details += "Nema dostupnih recenzija za ovaj proizvod.\n"
        prompt_details += "---\n"

    prompt_details += (
        "\nNa temelju gore navedenih informacija, odaberi najbolji proizvod koji zadovoljava korisnikove kriterije i budžet. "
        "U svojoj odluci, kratko obrazloži zašto je taj proizvod najbolji izbor. "
        "Ako nijedan proizvod nije zadovoljavajući, objasni zašto."
    )

    print("\n--- Prompt za finalnu odluku ---")
    print(prompt_details[:1000] + "..." if len(prompt_details) > 1000 else prompt_details) # Ispis dijela prompta
    print("--- Kraj prompta za finalnu odluku ---\n")

    # Pozivamo LLM (samog sebe ili drugog agenta) da donese odluku
    # U ovom slučaju, ovaj tool je dio glavnog agenta, pa bi se LLM pozvao interno
    # PydanticAI agent će ovo odraditi kao dio tool calling procesa
    # Ovdje moramo simulirati da LLM vraća BestBuyResult ili FailedSearch

    # Simulacija odluke LLM-a (za sada, najjeftiniji s pozitivnom recenzijom)
    best_product_candidate = None
    highest_rated_affordable_product = None
    min_price_overall = float('inf')

    for product in products:
        if product.price < min_price_overall: # Pratimo najjeftiniji
             min_price_overall = product.price

        product_reviews = all_reviews.get(product.id, [])
        avg_rating = 0
        num_reviews = 0
        if product_reviews:
            for r in product_reviews:
                if r.rating:
                    avg_rating += r.rating
                    num_reviews +=1
            if num_reviews > 0:
                avg_rating /= num_reviews

        if product.price <= search_criteria.budget:
            if avg_rating >= 4.0: # Preferiramo dobro ocijenjene
                if highest_rated_affordable_product is None or avg_rating > highest_rated_affordable_product['rating'] or \
                   (avg_rating == highest_rated_affordable_product['rating'] and product.price < highest_rated_affordable_product['product'].price):
                    highest_rated_affordable_product = {'product': product, 'rating': avg_rating}
            # Ako nema visoko ocijenjenih, uzimamo najjeftiniji
            if best_product_candidate is None or product.price < best_product_candidate.price :
                best_product_candidate = product


    if highest_rated_affordable_product:
        chosen_product = highest_rated_affordable_product['product']
        justification = f"Odabran zbog visoke prosječne ocjene ({highest_rated_affordable_product['rating']:.1f}/5.0) i cijene unutar budžeta."
        return BestBuyResult(
            product_name=chosen_product.name,
            price=chosen_product.price,
            currency=chosen_product.currency,
            webshop_name=chosen_product.webshop_name,
            product_url=chosen_product.url,
            justification=justification
        )
    elif best_product_candidate:
        # Ako nema visoko ocijenjenih, ali ima unutar budžeta
        chosen_product = best_product_candidate
        justification = "Odabran kao najpovoljnija opcija unutar budžeta. Nema dovoljno visoko ocijenjenih recenzija za druge opcije."
        return BestBuyResult(
            product_name=chosen_product.name,
            price=chosen_product.price,
            currency=chosen_product.currency,
            webshop_name=chosen_product.webshop_name,
            product_url=chosen_product.url,
            justification=justification
        )

    return FailedSearch(reason=f"Nakon analize, nijedan proizvod nije u potpunosti zadovoljio sve kriterije i budžet. Najniža pronađena cijena bila je {min_price_overall} EUR.")


# --- Glavni CLI tok ---

async def best_buy_workflow(user_query: str):
    """
    Orkestrira cijeli proces pronalaženja najbolje kupovine.
    """
    print(f"\nPokrećem BestBuy workflow za upit: '{user_query}'")
    history: List[ModelMessage] = [] # Za praćenje konverzacije s agentom

    try:
        # Korak 1: Agent interpretira korisnikov upit i izdvaja kriterije
        # Ovo bi se moglo napraviti s output_type=SearchCriteria
        # Za jednostavnost, sada ćemo to preskočiti i direktno kreirati SearchCriteria
        # U stvarnosti, prvi `run` bi bio za ekstrakciju kriterija.
        # result_criteria = await best_buy_agent.run(
        #     user_query,
        #     output_type=SearchCriteria,
        #     message_history=history
        # )
        # history.extend(result_criteria.all_messages())
        # if isinstance(result_criteria.output, SearchCriteria):
        #    search_criteria = result_criteria.output
        # else:
        #    print("Nisam uspio razumjeti kriterije pretrage.")
        #    return

        # Simulacija izvađenih kriterija (za sada hardkodirano iz primjera upita)
        # "Hoću kupiti best buy bluetooth slušalice za android u hrvatskoj, imam 100 EUR."
        if "bluetooth slušalice" in user_query.lower() and "100 eur" in user_query.lower():
             search_criteria = SearchCriteria(
                product_type="bluetooth slušalice za android",
                budget=100.0,
                country="Hrvatska"
            )
        else:
            # Ako ne možemo parsirati, tražimo od korisnika da specificira
            print("Molim vas specificirajte tip proizvoda, budžet i državu.")
            # Ovdje bi se moglo pitati agenta da postavi pitanja korisniku
            return

        print(f"\nDefinirani kriteriji pretrage: {search_criteria.model_dump_json(indent=2)}")

        # Korak 2: Agent pronalazi webshopove
        # Mora se specificirati output_type za tool call ako nije implicitno iz return type-a alata
        run_result_webshops = await best_buy_agent.run(
            f"Pronađi webshopove za {search_criteria.product_type} u {search_criteria.country}",
            # output_type=List[Webshop] # Agent će ovo skužiti iz tool-a
            message_history=history
        )
        history.extend(run_result_webshops.new_messages()) # Dodajemo samo nove poruke iz ovog koraka

        webshops: List[Webshop] = []
        if run_result_webshops.tool_calls: # Provjeravamo je li alat pozvan i vratio podatke
            for tc in run_result_webshops.tool_calls:
                if tc.tool_name == "find_webshops" and tc.result:
                    # tc.result je string, treba ga parsirati u List[Webshop]
                    # PydanticAI bi ovo trebao automatski odraditi ako je tool dobro definiran
                    # s povratnim tipom List[Webshop]
                    # Ako je `result` već parsiran objekt (npr. ako je alat interno pozvan s pravim tipom)
                    if isinstance(tc.result, list) and all(isinstance(item, Webshop) for item in tc.result):
                        webshops.extend(tc.result)
                    else: # Fallback ako je string, pokušaj parsirati (ovo je grubo)
                        try:
                            parsed_result = json.loads(tc.result)
                            webshops.extend([Webshop(**item) for item in parsed_result])
                        except json.JSONDecodeError:
                            print(f"Greška pri parsiranju rezultata alata find_webshops: {tc.result}")
        elif isinstance(run_result_webshops.output, list) and all(isinstance(item, Webshop) for item in run_result_webshops.output):
             webshops = run_result_webshops.output # Ako je agent direktno vratio listu webshopova

        if not webshops:
            print("Nije pronađen nijedan relevantan webshop.")
            return
        print(f"\nPronađeni webshopovi ({len(webshops)}):")
        for ws in webshops:
            print(f"- {ws.name} ({ws.url})")


        # Korak 3: Agent pregledava webshopove za proizvode
        all_found_products: List[Product] = []
        for webshop in webshops:
            run_result_products = await best_buy_agent.run(
                (f"Pregledaj webshop {webshop.name} ({webshop.url}) i pronađi proizvode "
                 f"koji odgovaraju kriterijima: {search_criteria.model_dump_json()}"),
                message_history=history
            )
            history.extend(run_result_products.new_messages())

            if run_result_products.tool_calls:
                 for tc in run_result_products.tool_calls:
                    if tc.tool_name == "crawl_webshop_for_products" and tc.result:
                        if isinstance(tc.result, list) and all(isinstance(item, Product) for item in tc.result):
                            all_found_products.extend(tc.result)
                        else:
                            try:
                                parsed_result = json.loads(tc.result)
                                all_found_products.extend([Product(**item) for item in parsed_result])
                            except json.JSONDecodeError:
                                print(f"Greška pri parsiranju rezultata alata crawl_webshop_for_products za {webshop.name}: {tc.result}")

        if not all_found_products:
            print("\nNije pronađen nijedan proizvod na webshopovima prema kriterijima.")
            return
        print(f"\nPronađeno ukupno proizvoda ({len(all_found_products)}):")
        for prod in all_found_products:
            print(f"- {prod.name} ({prod.price} {prod.currency}) na {prod.webshop_name}")


        # Korak 4: Agent pronalazi recenzije za svaki proizvod
        all_product_reviews: Dict[str, List[Review]] = {} # product_id -> List[Review]
        for product in all_found_products:
            run_result_reviews = await best_buy_agent.run(
                f"Pronađi recenzije za proizvod '{product.name}' (ID: {product.id})",
                message_history=history
            )
            history.extend(run_result_reviews.new_messages())
            product_reviews_list = []
            if run_result_reviews.tool_calls:
                for tc in run_result_reviews.tool_calls:
                    if tc.tool_name == "find_product_reviews" and tc.result:
                        if isinstance(tc.result, list) and all(isinstance(item, Review) for item in tc.result):
                            product_reviews_list.extend(tc.result)
                        else:
                            try:
                                parsed_result = json.loads(tc.result)
                                product_reviews_list.extend([Review(**item) for item in parsed_result])
                            except json.JSONDecodeError:
                                print(f"Greška pri parsiranju rezultata alata find_product_reviews za {product.name}: {tc.result}")
            all_product_reviews[product.id] = product_reviews_list
            if product_reviews_list:
                print(f"  Pronađeno {len(product_reviews_list)} recenzija za {product.name}")


        # Korak 5 & 6: Agent analizira recenzije i donosi odluku
        # Kreiramo prompt koji sadrži sve informacije
        decision_prompt = (
            f"Analiziraj sljedeće proizvode: {json.dumps([p.model_dump() for p in all_found_products])}, "
            f"njihove recenzije: {json.dumps({pid: [r.model_dump() for r in reviews] for pid, reviews in all_product_reviews.items()})} "
            f"i korisnikove kriterije: {search_criteria.model_dump_json()}. "
            f"Odluči koji je najbolji proizvod i vrati rezultat u formatu BestBuyResult ili FailedSearch."
        )

        run_result_decision = await best_buy_agent.run(
            decision_prompt,
            output_type=Union[BestBuyResult, FailedSearch], # Eksplicitno kažemo što očekujemo
            message_history=history
        )
        history.extend(run_result_decision.new_messages())

        final_decision = run_result_decision.output

        if isinstance(final_decision, BestBuyResult):
            print("\n--- Najbolja Kupovina ---")
            print(f"Proizvod: {final_decision.product_name}")
            print(f"Cijena: {final_decision.price} {final_decision.currency}")
            print(f"Webshop: {final_decision.webshop_name}")
            print(f"Link: {final_decision.product_url}")
            print(f"Obrazloženje: {final_decision.justification}")
        elif isinstance(final_decision, FailedSearch):
            print("\n--- Pretraga Nije Uspjela ---")
            print(f"Razlog: {final_decision.reason}")
        else:
            # Ako LLM nije vratio očekivani format, ispisujemo sirovi output
            print("\n--- Neočekivani Odgovor Agenta ---")
            print(final_decision)


        # Korak 7: Brisanje memorije (opcionalno, ovisno o MCP memory serveru)
        memory_client = best_buy_agent.mcp_clients.get('memory_server') # Dohvat klijenta po imenu
        if memory_client:
            try:
                # Ovo je placeholder, stvarna metoda ovisi o implementaciji MCP memory servera
                # await memory_client.clear_all_data_for_session(session_id="trenutna_sesija")
                print("\nMemorija (ako je primjenjivo) bi se sada obrisala.")
            except Exception as e:
                print(f"Greška pri brisanju memorije: {e}")


    except Exception as e:
        print(f"\nDošlo je do greške tijekom BestBuy workflowa: {e}")
        import traceback
        traceback.print_exc()


async def main_cli():
    print("Dobrodošli u BestBuy AI Agent!")
    print("Unesite 'exit' za izlaz.")

    # Pokretanje MCP servera u pozadini ako je potrebno (MCPServerStdio to radi automatski)
    # Nije potrebno eksplicitno `await agent.run_mcp_servers()` ako se MCPServerStdio koristi
    # i ako agent koristi te servere kroz svoje alate.
    # Kontekst `async with agent.run_mcp_servers():` je koristan ako se klijenti dohvaćaju
    # izvan `RunContext`-a alata. Za sada, pretpostavljamo da će alati dobiti klijente.

    while True:
        user_input = input("\nŠto želite kupiti? (npr. 'best buy bluetooth slušalice za android u hrvatskoj, imam 100 EUR'): \n> ")
        if user_input.lower() == 'exit':
            break
        if not user_input.strip():
            continue

        await best_buy_workflow(user_input)

    print("Hvala što ste koristili BestBuy AI Agenta. Doviđenja!")


if __name__ == "__main__":
    if GROQ_API_KEY and FIRECRAWL_API_KEY : # Osnovna provjera
        asyncio.run(main_cli())
    else:
        print("Molim postavite GROQ_API_KEY i FIRECRAWL_API_KEY environment varijable za pokretanje agenta.")