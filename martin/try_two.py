import os
import json
import base64
import sys
import time
import csv
import re
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Check if required packages are installed
required_packages = [
    'google-auth', 'google-auth-oauthlib', 'google-api-python-client',
    'requests', 'beautifulsoup4', 'serpapi', 'sqlite3', 'pandas', 'tavily-python'
]
try:
    import google.auth
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    import requests
    from bs4 import BeautifulSoup
    import pandas as pd
    import sqlite3
    from serpapi import GoogleSearch
    from tavily import TavilyClient
except ImportError:
    print("Installing required packages...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install"] + required_packages)
    # Reimport after installation
    import google.auth
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    import requests
    from bs4 import BeautifulSoup
    import pandas as pd
    import sqlite3
    from serpapi import GoogleSearch
    from tavily import TavilyClient

# Gmail API setup
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly', 
          'https://www.googleapis.com/auth/gmail.send',
          'https://www.googleapis.com/auth/gmail.modify']

def setup_gmail_api():
    """Set up Gmail API credentials and return the service."""
    creds = None
    # The file token.json stores the user's access and refresh tokens
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_info(
            json.loads(open('token.json').read()), SCOPES)
    
    # If there are no valid credentials, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                print("Error: credentials.json file not found.")
                print("Please download your OAuth 2.0 credentials from Google Cloud Console")
                print("and save them as 'credentials.json' in the current directory.")
                sys.exit(1)
            
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    
    # Build the Gmail service
    service = build('gmail', 'v1', credentials=creds)
    return service

class GmailAPI:
    def __init__(self):
        self.service = setup_gmail_api()
        # Set default recipient for all emails
        self.default_recipient = "martin.capo130@gmail.com"
    
    def list_messages(self, max_results=10, query=None):
        """List messages in the user's mailbox."""
        try:
            # Get messages from inbox
            results = self.service.users().messages().list(
                userId='me', 
                maxResults=max_results,
                q=query
            ).execute()
            
            messages = results.get('messages', [])
            
            if not messages:
                return "No messages found."
            
            message_list = []
            for message in messages:
                msg = self.service.users().messages().get(
                    userId='me', 
                    id=message['id'],
                    format='metadata',
                    metadataHeaders=['Subject', 'From', 'Date']
                ).execute()
                
                headers = msg['payload']['headers']
                subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
                sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
                date = next((h['value'] for h in headers if h['name'] == 'Date'), 'Unknown')
                
                message_list.append({
                    'id': msg['id'],
                    'subject': subject,
                    'from': sender,
                    'date': date,
                    'snippet': msg.get('snippet', '')
                })
            
            return message_list
        except Exception as e:
            return f"Error listing messages: {str(e)}"
    
    def get_message(self, message_id):
        """Get a specific message by ID."""
        try:
            message = self.service.users().messages().get(
                userId='me', 
                id=message_id,
                format='full'
            ).execute()
            
            headers = message['payload']['headers']
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
            sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
            date = next((h['value'] for h in headers if h['name'] == 'Date'), 'Unknown')
            
            # Extract body
            body = ""
            if 'parts' in message['payload']:
                for part in message['payload']['parts']:
                    if part['mimeType'] == 'text/plain':
                        body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                        break
            elif 'body' in message['payload'] and 'data' in message['payload']['body']:
                body = base64.urlsafe_b64decode(message['payload']['body']['data']).decode('utf-8')
            
            return {
                'id': message['id'],
                'subject': subject,
                'from': sender,
                'date': date,
                'body': body
            }
        except Exception as e:
            return f"Error getting message: {str(e)}"
    
    def send_message(self, to, subject, body, auto_mode=False):
        """Send an email message."""
        try:
            # Always override recipient with default recipient
            actual_recipient = self.default_recipient
            
            message = MIMEMultipart()
            message['to'] = actual_recipient
            message['subject'] = subject
            
            # Add original intended recipient in the body for reference
            if to != actual_recipient:
                new_body = f"Originally intended for: {to}\n\n{body}"
            else:
                new_body = body
                
            msg = MIMEText(new_body)
            message.attach(msg)
            
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
            
            # In auto mode, skip confirmation
            if not auto_mode:
                print(f"\nPreparing to send email:")
                print(f"To: {actual_recipient} (originally for: {to})")
                print(f"Subject: {subject}")
                print(f"Body: {new_body}")
                confirm = input("\nSend this email? (yes/no): ")
                
                if confirm.lower() != 'yes':
                    return "Email sending cancelled."
            
            send_message = self.service.users().messages().send(
                userId='me', 
                body={'raw': raw_message}
            ).execute()
            
            return f"Email sent successfully to {actual_recipient}. Message ID: {send_message['id']}"
        except Exception as e:
            return f"Error sending message: {str(e)}"
    
    def check_for_responses(self, query, days=7):
        """Check for responses to our outreach emails."""
        try:
            # Calculate date for query
            date_limit = (datetime.now() - timedelta(days=days)).strftime('%Y/%m/%d')
            full_query = f"{query} after:{date_limit}"
            
            messages = self.list_messages(max_results=20, query=full_query)
            if isinstance(messages, str):
                return messages
            return messages
        except Exception as e:
            return f"Error checking responses: {str(e)}"

class TavilySearchAPI:
    def __init__(self, api_key=None):
        self.api_key = api_key
        if self.api_key:
            self.client = TavilyClient(api_key=self.api_key)
    
    def search(self, query, max_results=10, search_depth="basic"):
        """Search the web using Tavily API."""
        if not self.client:
            return {"error": "Tavily API key not found. Please set up your API key."}
        
        try:
            response = self.client.search(
                query=query,
                search_depth=search_depth,
                max_results=max_results
            )
            return response
        except Exception as e:
            return {"error": f"Tavily search error: {str(e)}"}
    
    def extract_company_info(self, query, include_industry=True):
        """Search for a company and extract relevant information."""
        search_query = query
        if include_industry:
            search_query += " company industry information"
            
        results = self.search(search_query, max_results=5)
        
        if "error" in results:
            return {"error": results["error"]}
        
        company_info = {
            "name": query,
            "description": "",
            "industry": "",
            "website": "",
            "contact_info": "",
            "source": "tavily"
        }
        
        # Extract information from search results
        if "results" in results:
            # Combine content from all results
            all_content = " ".join([r.get("content", "") for r in results.get("results", [])])
            
            # Extract website from URLs
            for result in results.get("results", []):
                url = result.get("url", "")
                if url and "wikipedia" not in url and "linkedin" not in url:
                    # Try to extract domain
                    try:
                        domain = url.split("//")[1].split("/")[0]
                        if domain.startswith("www."):
                            domain = domain[4:]
                        company_info["website"] = domain
                        break
                    except:
                        pass
            
            # Extract description (first 250 chars)
            if all_content:
                company_info["description"] = all_content[:250].strip()
            
            # Try to extract industry
            industry_patterns = [
                r"industry:\s*([^\.]+)",
                r"([^\.]+)\s+industry",
                r"specializes in\s+([^\.]+)"
            ]
            
            for pattern in industry_patterns:
                match = re.search(pattern, all_content, re.IGNORECASE)
                if match:
                    company_info["industry"] = match.group(1).strip()
                    break
            
            # Try to extract email
            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            emails = re.findall(email_pattern, all_content)
            if emails:
                company_info["contact_info"] = emails[0]
            
        return company_info

class SponsorFinder:
    def __init__(self, serp_api_key=None, tavily_api_key=None):
        self.serp_api_key = serp_api_key
        self.tavily = TavilySearchAPI(tavily_api_key)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
    def search_sponsors(self, project_description, industry=None, limit=10):
        """Search for potential sponsors based on project description."""
        # First try Tavily search if available
        if self.tavily.client:
            return self.tavily_search(project_description, industry, limit)
        elif self.serp_api_key:
            return self.serp_api_search(project_description, industry, limit)
        else:
            return self.basic_search(project_description, industry, limit)
    
    def tavily_search(self, project_description, industry=None, limit=10):
        """Search for sponsors using Tavily API."""
        companies = []
        
        # Generate search queries
        search_queries = [
            f"top companies sponsoring {project_description}",
            f"corporate sponsors for {project_description}",
            f"{industry} companies sponsoring events" if industry else "companies with sponsorship programs"
        ]
        
        for query in search_queries:
            try:
                print(f"Searching Tavily for: {query}")
                results = self.tavily.search(query, max_results=5)
                
                if "error" in results:
                    print(f"Tavily search error: {results['error']}")
                    continue
                
                # Process search results
                for result in results.get("results", []):
                    content = result.get("content", "")
                    
                    # Extract potential company names using regex
                    company_patterns = [
                        r'([A-Z][a-z]+ [A-Z][a-z]+)',  # Two capitalized words
                        r'([A-Z][a-zA-Z0-9]+ Inc\.?)', # Company with Inc.
                        r'([A-Z][a-zA-Z0-9]+ LLC\.?)', # Company with LLC
                        r'([A-Z][a-zA-Z0-9]+ Corp\.?)' # Company with Corp.
                    ]
                    
                    for pattern in company_patterns:
                        matches = re.findall(pattern, content)
                        for match in matches:
                            # Further research each potential company
                            company_info = self.tavily.extract_company_info(match)
                            
                            if "error" not in company_info:
                                # Guess email if not found
                                if not company_info.get("contact_info") and company_info.get("website"):
                                    email = self.guess_email(company_info["name"], company_info["website"])
                                    company_info["contact_info"] = email
                                
                                companies.append({
                                    'name': company_info["name"],
                                    'website': company_info.get("website", ""),
                                    'email': company_info.get("contact_info", ""),
                                    'description': company_info.get("description", ""),
                                    'industry': company_info.get("industry", industry if industry else ""),
                                    'source': 'tavily',
                                    'relevance_score': 0.8  # Higher score for Tavily results
                                })
                
                # Prevent rate limiting
                time.sleep(random.uniform(1, 2))
                
            except Exception as e:
                print(f"Error in Tavily search: {str(e)}")
                continue
        
        # Remove duplicates
        unique_companies = []
        seen_names = set()
        
        for company in companies:
            if company['name'] not in seen_names:
                seen_names.add(company['name'])
                unique_companies.append(company)
        
        return unique_companies[:limit]
    
    def basic_search(self, project_description, industry=None, limit=10):
        """Basic search using requests and BeautifulSoup."""
        companies = []
        
        # Generate search queries
        search_queries = [
            f"companies sponsoring {project_description}",
            f"sponsors for {project_description}",
            f"{industry} companies sponsoring events"
        ]
        
        for query in search_queries:
            query = query.replace(' ', '+')
            url = f"https://www.google.com/search?q={query}"
            
            try:
                response = requests.get(url, headers=self.headers)
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Extract company names from search results
                results = soup.find_all('div', {'class': 'g'})
                for result in results[:limit]:
                    try:
                        title_elem = result.find('h3')
                        link_elem = result.find('a')
                        
                        if title_elem and link_elem:
                            title = title_elem.text
                            link = link_elem.get('href')
                            
                            # Simple extraction of company name from title
                            company_name = self.extract_company_name(title)
                            if company_name:
                                company_website = self.extract_domain(link)
                                
                                companies.append({
                                    'name': company_name,
                                    'website': company_website,
                                    'description': title,
                                    'source': 'basic_search',
                                    'relevance_score': 0.5  # Default score
                                })
                    except Exception as e:
                        print(f"Error extracting company info: {str(e)}")
                        continue
                
                # Prevent rate limiting
                time.sleep(random.uniform(1, 3))
                
            except Exception as e:
                print(f"Error in basic search: {str(e)}")
                continue
        
        # Remove duplicates based on company name
        unique_companies = []
        seen_names = set()
        
        for company in companies:
            if company['name'] not in seen_names:
                seen_names.add(company['name'])
                unique_companies.append(company)
        
        return unique_companies[:limit]
    
    def serp_api_search(self, project_description, industry=None, limit=10):
        """Use SerpAPI for more reliable search results."""
        companies = []
        
        # Generate search queries
        search_queries = [
            f"companies sponsoring {project_description}",
            f"sponsors for {project_description}",
            f"{industry} companies sponsoring events"
        ]
        
        for query in search_queries:
            try:
                search_params = {
                    "engine": "google",
                    "q": query,
                    "api_key": self.serp_api_key,
                    "num": min(10, limit)
                }
                
                search = GoogleSearch(search_params)
                results = search.get_dict()
                
                # Extract organic results
                if "organic_results" in results:
                    for result in results["organic_results"]:
                        title = result.get("title", "")
                        link = result.get("link", "")
                        snippet = result.get("snippet", "")
                        
                        company_name = self.extract_company_name(title)
                        if not company_name:
                            company_name = self.extract_company_name(snippet)
                        
                        if company_name:
                            company_website = self.extract_domain(link)
                            email = self.guess_email(company_name, company_website)
                            
                            companies.append({
                                'name': company_name,
                                'website': company_website,
                                'email': email,
                                'description': snippet,
                                'source': 'serp_api',
                                'relevance_score': 0.7  # Higher score for SerpAPI results
                            })
                
                # Prevent rate limiting
                time.sleep(random.uniform(1, 2))
                
            except Exception as e:
                print(f"Error in SERP API search: {str(e)}")
                continue
        
        # Remove duplicates
        unique_companies = []
        seen_names = set()
        
        for company in companies:
            if company['name'] not in seen_names:
                seen_names.add(company['name'])
                unique_companies.append(company)
        
        return unique_companies[:limit]
    
    def extract_company_name(self, text):
        """Extract company name from text."""
        # Simple regex to find company names (could be improved)
        patterns = [
            r'([A-Z][a-z]+ [A-Z][a-z]+)',  # Two capitalized words
            r'([A-Z][a-zA-Z]+)',           # Single capitalized word
            r'([A-Z][a-zA-Z0-9]+ Inc\.?)', # Company with Inc.
            r'([A-Z][a-zA-Z0-9]+ LLC\.?)', # Company with LLC
            r'([A-Z][a-zA-Z0-9]+ Corp\.?)' # Company with Corp.
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        
        return None
    
    def extract_domain(self, url):
        """Extract domain from URL."""
        if not url:
            return None
        
        try:
            # Simple domain extraction
            domain = url.split('//')[1].split('/')[0]
            return domain
        except:
            return None
    
    def guess_email(self, company_name, domain):
        """Guess company email based on common patterns."""
        if not domain:
            return None
        
        # Remove LLC, Inc., Corp. from company name
        company_name = re.sub(r'\s(LLC|Inc\.|Corp\.?|Company)$', '', company_name)
        
        # Generate common patterns
        name_parts = company_name.lower().split()
        if len(name_parts) > 0:
            first_word = name_parts[0]
            email_patterns = [
                f"info@{domain}",
                f"contact@{domain}",
                f"sponsorship@{domain}",
                f"marketing@{domain}",
                f"{first_word}@{domain}"
            ]
            
            return email_patterns[0]  # Return first pattern as a guess
        
        return None
    
    def enrich_company_data(self, companies):
        """Enrich company data with additional information."""
        enriched_companies = []
        
        for company in companies:
            # Try to use Tavily for enrichment if available
            if self.tavily.client and company.get('name'):
                try:
                    print(f"Enriching data for {company['name']} using Tavily...")
                    tavily_info = self.tavily.extract_company_info(company['name'])
                    
                    if "error" not in tavily_info:
                        # Update with Tavily info if available
                        if tavily_info.get("description") and not company.get("description"):
                            company["description"] = tavily_info["description"]
                        
                        if tavily_info.get("industry") and not company.get("industry"):
                            company["industry"] = tavily_info["industry"]
                        
                        if tavily_info.get("website") and not company.get("website"):
                            company["website"] = tavily_info["website"]
                        
                        if tavily_info.get("contact_info") and not company.get("email"):
                            company["email"] = tavily_info["contact_info"]
                        
                except Exception as e:
                    print(f"Error enriching data with Tavily for {company['name']}: {str(e)}")
            
            # Fallback to website scraping if no Tavily or missing info
            if company.get('website') and (not company.get('description') or not company.get('email')):
                try:
                    url = f"https://{company['website']}"
                    response = requests.get(url, headers=self.headers, timeout=5)
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # Try to find contact info
                    contact_page_links = soup.find_all('a', text=re.compile('contact', re.I))
                    if contact_page_links:
                        # Enhance with contact info if needed
                        contact_url = contact_page_links[0].get('href')
                        if contact_url and not contact_url.startswith('http'):
                            contact_url = url + contact_url
                        
                        company['contact_page'] = contact_url
                    
                    # Update description if empty
                    if not company.get('description'):
                        meta_desc = soup.find('meta', {'name': 'description'})
                        if meta_desc:
                            company['description'] = meta_desc.get('content')
                    
                except Exception as e:
                    print(f"Error enriching data from website for {company['name']}: {str(e)}")
            
            # Increase relevance score for companies with complete info
            if company.get('email') and company.get('description'):
                company['relevance_score'] = min(1.0, company.get('relevance_score', 0) + 0.2)
            
            enriched_companies.append(company)
        
        return enriched_companies

# Rest of the classes remain the same as in the original code
class SponsorshipDatabase:
    def __init__(self, db_path="sponsorship.db"):
        self.db_path = db_path
        self.conn = None
        self.init_db()
    
    def init_db(self):
        """Initialize the database with necessary tables."""
        try:
            self.conn = sqlite3.connect(self.db_path)
            cursor = self.conn.cursor()
            
            # Create companies table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS companies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT,
                website TEXT,
                industry TEXT,
                description TEXT,
                contact_person TEXT,
                source TEXT,
                relevance_score REAL,
                date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            # Create outreach table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS outreach (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER,
                email_subject TEXT,
                email_body TEXT,
                status TEXT DEFAULT 'pending',
                date_sent TIMESTAMP,
                response_received BOOLEAN DEFAULT 0,
                response_date TIMESTAMP,
                response_content TEXT,
                followup_sent BOOLEAN DEFAULT 0,
                followup_date TIMESTAMP,
                FOREIGN KEY (company_id) REFERENCES companies (id)
            )
            ''')
            
            # Create projects table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                requirements TEXT,
                target_audience TEXT,
                budget REAL,
                timeline TEXT,
                date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error initializing database: {str(e)}")
            return False
    
    def add_company(self, name, email=None, website=None, industry=None, 
                   description=None, contact_person=None, source=None, relevance_score=0):
        """Add a company to the database."""
        try:
            cursor = self.conn.cursor()
            
            # Check if company already exists
            cursor.execute("SELECT id FROM companies WHERE name=? AND (email=? OR (email IS NULL AND ? IS NULL))",
                          (name, email, email))
            result = cursor.fetchone()
            
            if result:
                print(f"Company '{name}' already exists in database with ID {result[0]}")
                return result[0]
            
            cursor.execute('''
            INSERT INTO companies (name, email, website, industry, description, contact_person, source, relevance_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (name, email, website, industry, description, contact_person, source, relevance_score))
            
            self.conn.commit()
            return cursor.lastrowid
        except Exception as e:
            print(f"Error adding company: {str(e)}")
            return None
    
    def add_outreach(self, company_id, email_subject, email_body, status="pending"):
        """Record an outreach attempt."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
            INSERT INTO outreach (company_id, email_subject, email_body, status, date_sent)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (company_id, email_subject, email_body, status))
            
            self.conn.commit()
            return cursor.lastrowid
        except Exception as e:
            print(f"Error adding outreach: {str(e)}")
            return None
    
    def update_outreach_status(self, outreach_id, status, response_content=None):
        """Update the status of an outreach attempt."""
        try:
            cursor = self.conn.cursor()
            
            if status == "responded" and response_content:
                cursor.execute('''
                UPDATE outreach 
                SET status=?, response_received=1, response_date=CURRENT_TIMESTAMP, response_content=?
                WHERE id=?
                ''', (status, response_content, outreach_id))
            elif status == "followup_sent":
                cursor.execute('''
                UPDATE outreach 
                SET status=?, followup_sent=1, followup_date=CURRENT_TIMESTAMP
                WHERE id=?
                ''', (status, outreach_id))
            else:
                cursor.execute('''
                UPDATE outreach 
                SET status=?
                WHERE id=?
                ''', (status, outreach_id))
            
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error updating outreach status: {str(e)}")
            return False
    
    def get_pending_followups(self, days_since_sent=5):
        """Get list of outreaches that need follow-up."""
        try:
            cursor = self.conn.cursor()
            days_ago = datetime.now() - timedelta(days=days_since_sent)
            
            cursor.execute('''
            SELECT o.id, c.name, c.email, o.email_subject
            FROM outreach o
            JOIN companies c ON o.company_id = c.id
            WHERE o.status='sent' AND o.followup_sent=0 AND o.response_received=0
            AND datetime(o.date_sent) <= datetime(?)
            ''', (days_ago,))
            
            return cursor.fetchall()
        except Exception as e:
            print(f"Error getting pending followups: {str(e)}")
            return []
    
    def get_companies_for_outreach(self, limit=20, exclude_contacted=True):
        """Get companies that haven't been contacted yet."""
        try:
            cursor = self.conn.cursor()
            
            if exclude_contacted:
                query = '''
                SELECT c.id, c.name, c.email, c.website, c.industry, c.description, c.relevance_score
                FROM companies c
                LEFT JOIN outreach o ON c.id = o.company_id
                WHERE o.id IS NULL
                ORDER BY c.relevance_score DESC
                LIMIT ?
                '''
            else:
                query = '''
                SELECT id, name, email, website, industry, description, relevance_score
                FROM companies
                ORDER BY relevance_score DESC
                LIMIT ?
                '''
            
            cursor.execute(query, (limit,))
            return cursor.fetchall()
        except Exception as e:
            print(f"Error getting companies for outreach: {str(e)}")
            return []
    
    def get_company_by_id(self, company_id):
        """Get a company by ID."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
            SELECT id, name, email, website, industry, description, contact_person, source, relevance_score
            FROM companies
            WHERE id = ?
            ''', (company_id,))
            
            return cursor.fetchone()
        except Exception as e:
            print(f"Error getting company by id: {str(e)}")
            return None
    
    def search_companies(self, search_term):
        """Search for companies in the database."""
        try:
            cursor = self.conn.cursor()
            search_term = f"%{search_term}%"
            cursor.execute('''
            SELECT id, name, email, website, industry, description, relevance_score
            FROM companies
            WHERE name LIKE ? OR description LIKE ? OR industry LIKE ?
            ORDER BY relevance_score DESC
            ''', (search_term, search_term, search_term))
            
            return cursor.fetchall()
        except Exception as e:
            print(f"Error searching companies: {str(e)}")
            return []
    
    def add_project(self, name, description, requirements=None, target_audience=None, budget=None, timeline=None):
        """Add a new project to the database."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
            INSERT INTO projects (name, description, requirements, target_audience, budget, timeline)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (name, description, requirements, target_audience, budget, timeline))
            
            self.conn.commit()
            return cursor.lastrowid
        except Exception as e:
            print(f"Error adding project: {str(e)}")
            return None
    
    def get_projects(self, limit=10):
        """Get list of projects."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
            SELECT id, name, description, requirements, target_audience, budget, timeline
            FROM projects
            ORDER BY date_added DESC
            LIMIT ?
            ''', (limit,))
            
            return cursor.fetchall()
        except Exception as e:
            print(f"Error getting projects: {str(e)}")
            return []
    
    def export_companies_to_csv(self, filename="sponsor_companies.csv"):
        """Export companies to CSV file."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
            SELECT name, email, website, industry, description, contact_person, relevance_score
            FROM companies
            ORDER BY relevance_score DESC
            ''')
            
            rows = cursor.fetchall()
            headers = ["Name", "Email", "Website", "Industry", "Description", "Contact Person", "Relevance Score"]
            
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(headers)
                writer.writerows(rows)
            
            return len(rows)
        except Exception as e:
            print(f"Error exporting to CSV: {str(e)}")
            return 0
    
    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()

class SponsorOutreach:
    def __init__(self, gmail_api=None, db=None):
        self.gmail_api = gmail_api if gmail_api else GmailAPI()
        self.db = db if db else SponsorshipDatabase()
    
    def generate_outreach_email(self, company, project_name, project_description):
        """Generate a personalized outreach email."""
        company_name = company[1]  # Index 1 should be company name based on get_companies_for_outreach
        industry = company[4] if len(company) > 4 and company[4] else "your industry"
        
        subject = f"Sponsorship Opportunity: {project_name}"
        
        body = f"""Dear {company_name} Team,

I hope this email finds you well. I'm reaching out to discuss a potential sponsorship opportunity for {project_name}, a project that aligns well with {industry}.

About our project:
{project_description}

We believe this collaboration could provide valuable exposure for {company_name} while supporting an initiative that resonates with your brand values.

Would you be interested in discussing sponsorship options? I'd be happy to provide more details or schedule a call to explore this opportunity further.

Looking forward to your response.

Best regards,
Sponsorship Team
"""
        return subject, body
    
    def send_batch_outreach(self, project_name, project_description, batch_size=5, simulate=True):
        """Send outreach emails to a batch of companies."""
        companies = self.db.get_companies_for_outreach(limit=batch_size)
        sent_count = 0
        
        for company in companies:
            company_id = company[0]
            email = company[2]
            
            if not email:
                print(f"No email found for {company[1]}, skipping...")
                continue
            
            subject, body = self.generate_outreach_email(company, project_name, project_description)
            
            if simulate:
                print(f"\nSIMULATED EMAIL to {company[1]} <{email}>")
                print(f"Subject: {subject}")
                print(f"Body: \n{body}")
                print("---")
                status = "simulated"
            else:
                # Send actual email
                result = self.gmail_api.send_message(email, subject, body, auto_mode=True)
                print(result)
                
                if "successfully" in result:
                    status = "sent"
                else:
                    status = "failed"
            
            # Record the outreach attempt
            self.db.add_outreach(company_id, subject, body, status)
            sent_count += 1
            
            # Add delay between emails
            if not simulate and sent_count < len(companies):
                delay = random.uniform(10, 30)
                print(f"Waiting {delay:.1f} seconds before next email...")
                time.sleep(delay)
        
        return sent_count
    
    def generate_followup_email(self, company_name, original_subject):
        """Generate a follow-up email."""
        subject = f"Re: {original_subject}"
        
        body = f"""Dear {company_name} Team,

I wanted to follow up on my previous email regarding sponsorship opportunities for our project.

I understand you may be busy, but I believe this could be a valuable partnership opportunity. If you have any questions or would like additional information, please let me know.

Looking forward to hearing from you.

Best regards,
Sponsorship Team
"""
        return subject, body
    
    def send_followups(self, days_since_sent=7, simulate=True):
        """Send follow-up emails to companies that haven't responded."""
        followups = self.db.get_pending_followups(days_since_sent)
        sent_count = 0
        
        for followup in followups:
            outreach_id = followup[0]
            company_name = followup[1]
            email = followup[2]
            original_subject = followup[3]
            
            subject, body = self.generate_followup_email(company_name, original_subject)
            
            if simulate:
                print(f"\nSIMULATED FOLLOWUP to {company_name} <{email}>")
                print(f"Subject: {subject}")
                print(f"Body: \n{body}")
                print("---")
                success = True
            else:
                # Send actual email
                result = self.gmail_api.send_message(email, subject, body, auto_mode=True)
                print(result)
                success = "successfully" in result
            
            if success:
                self.db.update_outreach_status(outreach_id, "followup_sent")
                sent_count += 1
                
                # Add delay between emails
                if not simulate and sent_count < len(followups):
                    delay = random.uniform(10, 30)
                    print(f"Waiting {delay:.1f} seconds before next email...")
                    time.sleep(delay)
        
        return sent_count
    
    def check_responses(self):
        """Check for responses to outreach emails."""
        # Search for replies in the last 14 days
        responses = self.gmail_api.check_for_responses("sponsorship", days=14)
        
        if isinstance(responses, str):
            print(f"Error checking responses: {responses}")
            return 0
        
        processed = 0
        for response in responses:
            # Get email details
            message = self.gmail_api.get_message(response['id'])
            if isinstance(message, str):  # Error case
                continue
                
            # Extract company info from email
            sender = message['from']
            subject = message['subject']
            body = message['body']
            
            company_name = self.extract_company_from_email(sender)
            if not company_name:
                continue
                
            # Try to find matching outreach in database
            companies = self.db.search_companies(company_name)
            if not companies:
                print(f"No matching company found for response from {sender}")
                continue
                
            company_id = companies[0][0]  # Take first match
            
            # Get outreach records for this company
            cursor = self.db.conn.cursor()
            cursor.execute('''
            SELECT id FROM outreach WHERE company_id = ? AND status IN ('sent', 'followup_sent')
            ORDER BY date_sent DESC LIMIT 1
            ''', (company_id,))
            
            outreach = cursor.fetchone()
            if outreach:
                outreach_id = outreach[0]
                # Update the outreach record with response
                self.db.update_outreach_status(outreach_id, "responded", body)
                processed += 1
                print(f"Recorded response from {company_name}")
        
        return processed
    
    def extract_company_from_email(self, email_string):
        """Extract company name from email address or display name."""
        # Try to extract from name part: "Company Name <email@example.com>"
        name_match = re.match(r'([^<]+)<', email_string)
        if name_match:
            return name_match.group(1).strip()
        
        # Try to extract from domain
        domain_match = re.search(r'@([^>]+)', email_string)
        if domain_match:
            domain = domain_match.group(1).strip()
            # Remove .com, .org, etc.
            domain = domain.split('.')[0]
            return domain
        
        return None

class SponsorApp:
    def __init__(self):
        # Initialize all components
        print("Initializing SponsorFinder application...")
        
        # Check for API keys
        tavily_api_key = os.getenv('TAVILY_API_KEY')
        serp_api_key = None
        
        if os.path.exists('tavily_api_key.txt'):
            with open('tavily_api_key.txt', 'r') as f:
                tavily_api_key = f.read().strip()
                print("Tavily API key loaded.")
        else:
            print("No Tavily API key found. Create a file named 'tavily_api_key.txt' with your API key.")
        
        if os.path.exists('serp_api_key.txt'):
            with open('serp_api_key.txt', 'r') as f:
                serp_api_key = f.read().strip()
                print("SerpAPI key loaded.")
        
        # Initialize components
        self.gmail_api = GmailAPI()
        self.tavily_search = TavilySearchAPI(tavily_api_key)
        self.sponsor_finder = SponsorFinder(serp_api_key, tavily_api_key)
        self.db = SponsorshipDatabase()
        self.outreach = SponsorOutreach(self.gmail_api, self.db)
    
    def run_cli(self):
        """Run the command-line interface."""
        while True:
            print("\n==== SponsorFinder CLI ====")
            print("1. Search for potential sponsors")
            print("2. View companies in database")
            print("3. Create new project")
            print("4. View projects")
            print("5. Send batch outreach emails")
            print("6. Send follow-up emails")
            print("7. Check for responses")
            print("8. Export companies to CSV")
            print("9. Run automated workflow")
            print("10. Check sent emails")  # New option
            print("11. Exit")
            
            choice = input("\nSelect an option (1-11): ")
            
            if choice == '9':
                self.run_automated_workflow()
            elif choice == '1':
                self.search_sponsors()
            elif choice == '2':
                self.view_companies()
            elif choice == '3':
                self.create_project()
            elif choice == '4':
                self.view_projects()
            elif choice == '5':
                self.send_outreach()
            elif choice == '6':
                self.send_followups()
            elif choice == '7':
                self.check_responses()
            elif choice == '8':
                self.export_to_csv()
            elif choice == '10':
                self.check_sent_emails()  # New method call
            elif choice == '11':
                print("Exiting application. Goodbye!")
                self.db.close()
                break
            else:
                print("Invalid option. Please try again.")
    
    def search_sponsors(self):
        """Search for potential sponsors."""
        print("\n==== Search for Sponsors ====")
        project_desc = input("Enter project description: ")
        industry = input("Industry focus (optional): ")
        limit = int(input("Number of sponsors to find (default 10): ") or 10)
        
        print("\nSearching for sponsors... This may take a few minutes.")
        sponsors = self.sponsor_finder.search_sponsors(project_desc, industry, limit)
        
        if not sponsors:
            print("No sponsors found. Try a different search query.")
            return
        
        print(f"\nFound {len(sponsors)} potential sponsors.")
        print("Enriching company data...")
        sponsors = self.sponsor_finder.enrich_company_data(sponsors)
        
        for idx, sponsor in enumerate(sponsors, 1):
            print(f"\n{idx}. {sponsor['name']}")
            print(f"   Website: {sponsor.get('website', 'N/A')}")
            print(f"   Email: {sponsor.get('email', 'N/A')}")
            print(f"   Industry: {sponsor.get('industry', 'N/A')}")
            print(f"   Relevance: {sponsor.get('relevance_score', 0):.2f}")
            if sponsor.get('description'):
                desc = sponsor['description']
                print(f"   Description: {desc[:100]}..." if len(desc) > 100 else f"   Description: {desc}")
        
        save = input("\nSave these sponsors to database? (y/n): ")
        if save.lower() == 'y':
            saved_count = 0
            for sponsor in sponsors:
                sponsor_id = self.db.add_company(
                    name=sponsor['name'],
                    email=sponsor.get('email'),
                    website=sponsor.get('website'),
                    industry=sponsor.get('industry'),
                    description=sponsor.get('description'),
                    source=sponsor.get('source'),
                    relevance_score=sponsor.get('relevance_score', 0)
                )
                if sponsor_id:
                    saved_count += 1
            
            print(f"Saved {saved_count} sponsors to database.")
    
    def view_companies(self):
        """View companies in the database."""
        print("\n==== Companies in Database ====")
        search = input("Search term (leave empty for all): ")
        
        if search:
            companies = self.db.search_companies(search)
        else:
            companies = self.db.get_companies_for_outreach(limit=50, exclude_contacted=False)
        
        if not companies:
            print("No companies found.")
            return
        
        for idx, company in enumerate(companies, 1):
            print(f"\n{idx}. {company[1]}")  # company[1] is name
            print(f"   Email: {company[2] or 'N/A'}")
            print(f"   Website: {company[3] or 'N/A'}")
            print(f"   Industry: {company[4] or 'N/A'}")
            if company[5]:  # Description
                desc = company[5]
                print(f"   Description: {desc[:100]}..." if len(desc) > 100 else f"   Description: {desc}")
            print(f"   Relevance: {company[6]:.2f}" if company[6] else "   Relevance: N/A")
    
    def create_project(self):
        """Create a new project."""
        print("\n==== Create New Project ====")
        name = input("Project name: ")
        description = input("Project description: ")
        requirements = input("Requirements (optional): ")
        target_audience = input("Target audience (optional): ")
        
        budget_str = input("Budget (optional): ")
        budget = float(budget_str) if budget_str else None
        
        timeline = input("Timeline (optional): ")
        
        project_id = self.db.add_project(name, description, requirements, target_audience, budget, timeline)
        
        if project_id:
            print(f"Project '{name}' created successfully with ID {project_id}.")
        else:
            print("Failed to create project.")
    
    def view_projects(self):
        """View projects in the database."""
        print("\n==== Projects ====")
        projects = self.db.get_projects()
        
        if not projects:
            print("No projects found.")
            return
        
        for idx, project in enumerate(projects, 1):
            print(f"\n{idx}. {project[1]}")  # project[1] is name
            print(f"   Description: {project[2]}")
            if project[3]:  # Requirements
                print(f"   Requirements: {project[3]}")
            if project[4]:  # Target audience
                print(f"   Target audience: {project[4]}")
            if project[5]:  # Budget
                print(f"   Budget: ${project[5]}")
            if project[6]:  # Timeline
                print(f"   Timeline: {project[6]}")
    
    def send_outreach(self):
        """Send batch outreach emails."""
        print("\n==== Send Outreach Emails ====")
        
        # Display available projects
        projects = self.db.get_projects()
        if not projects:
            print("No projects found. Create a project first.")
            return
        
        print("Available projects:")
        for idx, project in enumerate(projects, 1):
            print(f"{idx}. {project[1]}")
        
        project_idx = int(input("\nSelect project number: ")) - 1
        if project_idx < 0 or project_idx >= len(projects):
            print("Invalid project number.")
            return
        
        project = projects[project_idx]
        project_name = project[1]
        project_description = project[2]
        
        batch_size = int(input("Number of companies to contact (1-20): ") or 5)
        batch_size = max(1, min(20, batch_size))  # Ensure between 1 and 20
        
        simulate = input("Simulate emails? (yes/no, default: yes): ").lower() != 'no'
        
        if not simulate:
            confirm = input(f"This will send REAL emails to {batch_size} companies. Continue? (yes/no): ")
            if confirm.lower() != 'yes':
                print("Operation cancelled.")
                return
        
        sent_count = self.outreach.send_batch_outreach(
            project_name, project_description, batch_size, simulate)
        
        mode = "Simulated" if simulate else "Sent"
        print(f"\n{mode} {sent_count} outreach emails.")
    
    def send_followups(self):
        """Send follow-up emails."""
        print("\n==== Send Follow-up Emails ====")
        
        days = int(input("Days since initial email (default: 7): ") or 7)
        simulate = input("Simulate emails? (yes/no, default: yes): ").lower() != 'no'
        
        if not simulate:
            confirm = input("This will send REAL follow-up emails. Continue? (yes/no): ")
            if confirm.lower() != 'yes':
                print("Operation cancelled.")
                return
        
        sent_count = self.outreach.send_followups(days, simulate)
        
        mode = "Simulated" if simulate else "Sent"
        print(f"\n{mode} {sent_count} follow-up emails.")
    
    def check_responses(self):
        """Check for email responses."""
        print("\n==== Check for Responses ====")
        print("Checking Gmail for responses...")
        
        processed = self.outreach.check_responses()
        print(f"Processed {processed} new responses.")
    
    def export_to_csv(self):
        """Export companies to CSV."""
        print("\n==== Export Companies to CSV ====")
        filename = input("Filename (default: sponsor_companies.csv): ") or "sponsor_companies.csv"
        
        count = self.db.export_companies_to_csv(filename)
        if count > 0:
            print(f"Exported {count} companies to {filename}.")
        else:
            print("No companies exported.")
    
    # Add this method to the SponsorApp class
    def run_automated_workflow(self):
        """Run an automated sponsorship outreach workflow."""
        print("\n==== Automated Sponsorship Outreach ====")
        
        # 1. Get project details
        print("\nProject Details:")
        name = input("Project name: ")
        description = input("Project description: ")
        target_audience = input("Target audience: ")
        
        # 2. Create project in database
        project_id = self.db.add_project(
            name=name,
            description=description,
            target_audience=target_audience
        )
        
        # 3. Search for potential sponsors
        print("\nSearching for potential sponsors...")
        sponsors = self.sponsor_finder.search_sponsors(
            project_description=description,
            industry=target_audience,
            limit=20
        )
        
        if not sponsors:
            print("No potential sponsors found.")
            return
        
        # 4. Enrich and save sponsor data
        print(f"Found {len(sponsors)} potential sponsors. Enriching data...")
        enriched_sponsors = self.sponsor_finder.enrich_company_data(sponsors)
        
        saved_count = 0
        for sponsor in enriched_sponsors:
            sponsor_id = self.db.add_company(
                name=sponsor['name'],
                email=sponsor.get('email'),
                website=sponsor.get('website'),
                industry=sponsor.get('industry'),
                description=sponsor.get('description'),
                source=sponsor.get('source'),
                relevance_score=sponsor.get('relevance_score', 0)
            )
            if sponsor_id:
                saved_count += 1
        
        print(f"\nSaved {saved_count} sponsors to database.")
        
        # 5. Send initial outreach
        print("\nPreparing to send outreach emails...")
        simulate = input("Simulate emails? (yes/no, default: yes): ").lower() != 'no'
        
        if not simulate:
            confirm = input(f"This will send REAL emails to {saved_count} companies. Continue? (yes/no): ")
            if confirm.lower() != 'yes':
                print("Operation cancelled.")
                return
        
        sent_count = self.outreach.send_batch_outreach(
            project_name=name,
            project_description=description,
            batch_size=saved_count,
            simulate=simulate
        )
        
        mode = "Simulated" if simulate else "Sent"
        print(f"\n{mode} {sent_count} outreach emails.")
        
        # 6. Schedule follow-ups
        print("\nScheduling follow-ups for non-responsive companies in 7 days...")
        print("Use option 6 from the main menu to send follow-ups when ready.")

    def check_sent_emails(self):
        """View sent emails from Gmail account."""
        print("\n==== Sent Emails ====")
        
        # Number of days to look back
        days = int(input("Check emails from how many days ago? (default: 7): ") or 7)
        
        print("\nFetching sent emails...")
        try:
            # Search for sent emails using Gmail API
            query = f"in:sent after:{(datetime.now() - timedelta(days=days)).strftime('%Y/%m/%d')}"
            messages = self.gmail_api.list_messages(max_results=50, query=query)
            
            if isinstance(messages, str):
                print(f"Error: {messages}")
                return
            
            if not messages:
                print("No sent emails found in the specified time period.")
                return
            
            print(f"\nFound {len(messages)} sent emails:\n")
            for idx, message in enumerate(messages, 1):
                print(f"{idx}. Date: {message['date']}")
                print(f"   To: {message['from']}")  # 'from' contains recipient in sent emails
                print(f"   Subject: {message['subject']}")
                print(f"   Snippet: {message['snippet'][:100]}...")
                print()
                
            # Option to view full email content
            while True:
                choice = input("\nEnter email number to view full content (or 0 to return): ")
                if choice == '0':
                    break
                    
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(messages):
                        full_message = self.gmail_api.get_message(messages[idx]['id'])
                        print("\nFull Email Content:")
                        print(f"Date: {full_message['date']}")
                        print(f"To: {full_message['from']}")
                        print(f"Subject: {full_message['subject']}")
                        print("\nBody:")
                        print(full_message['body'])
                    else:
                        print("Invalid email number.")
                except ValueError:
                    print("Invalid input. Please enter a number.")
                    
        except Exception as e:
            print(f"Error checking sent emails: {str(e)}")

def main():
    app = SponsorApp()
    app.run_cli()

if __name__ == "__main__":
    main()