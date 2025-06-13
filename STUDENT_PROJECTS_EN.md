# Student Project Tasks

    agents that do boring things instead of humans

    people don't do these things at all because they're boring, but they would be useful to them

    useful products that could be monetized

    startup potential

**MVP**

MVP (Minimum Viable Product) is the most basic version of a product that has enough functionality to satisfy early users and enable gathering feedback for future development.

Key characteristics of MVP:

- Contains only basic functions necessary to solve the main user problem
- Focuses on the key value that the product provides
- Enables quick market entry and idea testing
- Serves as a foundation for iterative development based on feedback
- Reduces development risk and costs

The purpose of MVP development is to test product hypotheses with real users with minimal resource investment. After launch, the team collects usage data and feedback that helps in making decisions about future development.

## 1. Social Account Promotion
    
    Agent conducts a promotional campaign for a product or service.

**MVP**
- we specify the product and create a social account
- agent periodically writes and publishes promotional texts for that product

    **Required tools**
    - MCP server for social platform   

**Possible improvements**
- agent plans the entire campaign in advance
- agent follows new trends
- generating and publishing image and video posts
- monitoring comments and responding to them
- human in the loop
- analytics


## 2. Finding Sponsors or Investors
    
    Agent finds potentially interested parties and sends them sponsorship inquiries.

**MVP**
- we describe what we need sponsorship for, agent searches the web for companies that might have interest or desire to sponsor
- writes and sends them sponsorship inquiries

    **Required tools**
    - email
    - database
    - web search and scraping  

**Possible improvements**
- agent looks for companies that have already sponsored such things
- agent monitors responses and either responds itself when needed or notifies a human about interesting responses
- expansion to social media

## 3. Finding Best Buys
    
    When you need to buy something, you set a budget and the agent finds the best product for that price

**MVP**
- you specify criteria that are important to you for the product
- agent searches webshops for the best product for that price

    **Required tools**
    - code execution
    - memory
    - web search and scraping  

**Possible improvements**
- analysis of reviews and comments about products
- expansion to social marketplace
- search of physical stores nearby
- phone agent that can call stores and talk to merchants
- agent can order the product itself

## 4. Exceptional Opportunity

    Agent monitors the market and notifies you when an unusually cheap product appears

**MVP**
- you specify a product you're interested in
- agent monitors one classified ads site and calculates the average value of a product using some algorithm. when something appears that deviates from the average in price, it notifies you

    **Required tools**
    - code execution
    - database, memory
    - web search and scraping
    - email or IM integration

**Possible improvements**
- monitoring multiple products
- finding and adding classified ads sites based on location
- expansion to social marketplace
- adding criteria that define deviation from average

## 5. Saving Receipts to Database

    Agent converts receipt images into database records

**MVP**
- you want to track and analyze spending, or have an archive
- you photograph a series of receipts, agent reads them and saves the data you want to the database

    **Required tools**
    - database
    - filesystem
    - image reading

**Possible improvements**
- consumer behavior analysis
- savings advice
- expansion to other documents, not just receipts

## 6. Filling Data in Documents

    Agent fills specified fields in a document with data from multiple other documents

**MVP**
- concrete problem in a bank
- agent analyzes the template of the target Word document to see what data needs to be filled, finds that data in multiple other documents and creates a new one with filled data

    **Required tools**
    - filesystem
    - reading Excel, PDF, Word files
    - generating Word documents

**Possible improvements**
- expansion to other types of documents
- searching for required data in databases, intranet, other sources
