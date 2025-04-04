# Zadaci za radove

    agenti koji rade dosadne stvari umjesto ljudi

    ljudi te stvari uopće ne rade jer su dosadne, a bile bi im korisne

    korisni proizvodi koji bi se mogli monetizirati

    potencijal za startup

**MVP**

MVP (Minimum Viable Product) je najosnovnija verzija proizvoda koja ima dovoljno funkcionalnosti da zadovolji rane korisnike i omogući prikupljanje povratnih informacija za budući razvoj.

Ključne karakteristike MVP-a:

- Sadrži samo osnovne funkcije neophodne za rješavanje glavnog problema korisnika
- Fokusira se na ključnu vrijednost koju proizvod pruža
- Omogućava brz izlazak na tržište i testiranje ideje
- Služi kao osnova za iterativni razvoj na temelju povratnih informacija
- Smanjuje rizik i troškove razvoja

Svrha razvoja MVP-a je testirati hipoteze o proizvodu sa stvarnim korisnicima uz minimalno ulaganje resursa. Nakon lansiranja, tim prikuplja podatke o korištenju i povratne informacije koje pomažu u donošenju odluka o budućem razvoju.

## 1. Promocija na social accountu
    
    Agent provodi kampanju promocije za neki proizvod ili uslugu.

**MVP**
- zadamo proizvod i napravimo social account
- agent periodično piše i objavljuje tekstove za promociju tog proizvoda

    **Potrebni alati**
    - MCP server za social platformu   

**Moguća poboljšanja**
- agent isplanira cijelu kampanju unaprijed
- agent prati nove trendove
- generiranje i objava slikovnih i video postova
- praćenje komentara i odgovaranje na njih
- human in the loop
- analitika


## 2. Traženje sponzora ili investitora
    
    Agent nađe potencijalno zainteresirane stranke i šalje im upit za sponzoriranje.

**MVP**
- opišemo za šta nam treba sponzorstvo, agent pretraži web za firme koje bi mogle imati interesa ili želje za sponzoriranje 
- napiše i pošalje im upite za sponzorstvo

    **Potrebni alati**
    - email
    - baza
    - web search i scraping  

**Moguća poboljšanja**
- agent traži firme koje su već sponzorirale takve stvari
- agent prati odgovore i po potrebi ili sam odgovori ili obavijesti čovjeka o zanimljivom odgovoru
- proširenje na social

## 3. Traženje best buya
    
    Kada trebate kupiti nešto, zadate buđet i agent nađe najbolji proizvod za tu cijenu

**MVP**
- zadate kriterije koji su vam bitni kod proizvoda
- agent pretraži webshopove za najbolji proizvod za tu cijenu

    **Potrebni alati**
    - izvršavanje koda
    - memorija
    - web search i scraping  

**Moguća poboljšanja**
- analiza reviewa i komentara o proizvodima
- proširenje na social marketplace
- pretraga fizičkih prodavaonica u blizini
- telefonski agent koji može nazvati dućane i razgovarati s trgovcima, 
- agent može sam naručiti proizvod

## 4. Iznimna prilika

    Agent prati tržište i obavijesti vas kada se pojavi neuobičajeno jeftin proizvod

**MVP**
- zadate proizvod koji vas zanima
- agent prati jedan oglasnik i po nekom algoritmu računa prosječnu vrijednost nekog proizvoda. kad se pojavi nešto šta cijenom odskače od prosjeka, obavijesti vas

    **Potrebni alati**
    - izvršavanje koda
    - baza, memorija
    - web search i scraping
    - email ili IM integracija

**Moguća poboljšanja**
- praćenje više proizvoda
- trazanje i dodavajne oglasnika bazirano na lokaciji
- proširenje na social marketplace
- dodavanje kriterija kojima se definira odstupanje od prosjeka

## 5. Spremanje računa u bazu

    Agent pretvara slike računa u zapise u bazi

**MVP**
- želite pratiti i analizirati potrošnju, ili imati arhivu
- uslikate seriju računa, agent ih pročita i spremi u bazu podatke koje želite

    **Potrebni alati**
    - baza
    - filesystem
    - čitanje slika

**Moguća poboljšanja**
- analiza potrošačkog ponašanja
- savjeti o štednji
- proširenje na druge dokumente, ne samo račune

## 6. Popunjavanjne podataka u dokumentu

    Agent popuni zadana polja u dokumentu podacima iz više drugih dokumenata

**MVP**
- konkretan problem u banci
- agent analizira template ciljnog word dokumenta da vidi koje podatke treba popuniti, nađe te podatke u više drugih dokumenata i napravi novi s popunjenim podacima

    **Potrebni alati**
    - filesystem
    - čitanje excela, PDFa, worda
    - generiranje word dokumenta

**Moguća poboljšanja**
- proširenje na druge vrste dokumenata
- traženje potrebnih podataka u bazi, intrawebu, drugim izvorima


