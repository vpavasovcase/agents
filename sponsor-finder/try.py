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

# Check if required packages are installed
required_packages = [
    'google-auth', 'google-auth-oauthlib', 'google-api-python-client',
    'requests', 'beautifulsoup4', 'serpapi', 'sqlite3', 'pandas'
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
            message = MIMEMultipart()
            message['to'] = to
            message['subject'] = subject
            
            msg = MIMEText(body)
            message.attach(msg)
            
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
            
            # In auto mode, skip confirmation
            if not auto_mode:
                print(f"\nPreparing to send email:")
                print(f"To: {to}")
                print(f"Subject: {subject}")
                print(f"Body: {body}")
                confirm = input("\nSend this email? (yes/no): ")
                
                if confirm.lower() != 'yes':
                    return "Email sending cancelled."
            
            send_message = self.service.users().messages().send(
                userId='me', 
                body={'raw': raw_message}
            ).execute()
            
            return f"Email sent successfully. Message ID: {send_message['id']}"
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
                cursor.execute('''
                SELECT c.id, c.name, c.email, c.website, c.industry, c.relevance_score
                FROM companies c
                LEFT JOIN outreach o ON c.id = o.company_id
                WHERE o.id IS NULL AND c.email IS NOT NULL
                ORDER BY c.relevance_score DESC
                LIMIT ?
                ''', (limit,))
            else:
                cursor.execute('''
                SELECT id, name, email, website, industry, relevance_score
                FROM companies
                WHERE email IS NOT NULL
                ORDER BY relevance_score DESC
                LIMIT ?
                ''', (limit,))
            
            return cursor.fetchall()
        except Exception as e:
            print(f"Error getting companies for outreach: {str(e)}")
            return []
    
    def add_project(self, name, description=None, requirements=None, 
                    target_audience=None, budget=None, timeline=None):
        """Add a project to the database."""
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
    
    def get_project(self, project_id):
        """Get project details."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
            SELECT * FROM projects WHERE id=?
            ''', (project_id,))
            
            columns = [column[0] for column in cursor.description]
            project = dict(zip(columns, cursor.fetchone()))
            return project
        except Exception as e:
            print(f"Error getting project: {str(e)}")
            return None
    
    def get_all_projects(self):
        """Get all projects."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT id, name, description FROM projects ORDER BY date_added DESC')
            return cursor.fetchall()
        except Exception as e:
            print(f"Error getting projects: {str(e)}")
            return []
    
    def export_to_csv(self, table_name, filename=None):
        """Export a table to CSV."""
        if filename is None:
            filename = f"{table_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        try:
            df = pd.read_sql_query(f"SELECT * FROM {table_name}", self.conn)
            df.to_csv(filename, index=False)
            return filename
        except Exception as e:
            print(f"Error exporting to CSV: {str(e)}")
            return None
    
    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()

class SponsorFinder:
    def __init__(self, serp_api_key=None):
        self.serp_api_key = serp_api_key
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
    def search_sponsors(self, project_description, industry=None, limit=10):
        """Search for potential sponsors based on project description."""
        if not self.serp_api_key:
            return self.basic_search(project_description, industry, limit)
        else:
            return self.serp_api_search(project_description, industry, limit)
    
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
            # Try to get more info from company website
            if company.get('website'):
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
                    
                    # Increase relevance score for companies with complete info
                    if company.get('email') and company.get('description'):
                        company['relevance_score'] = min(1.0, company.get('relevance_score', 0) + 0.2)
                    
                except Exception as e:
                    print(f"Error enriching data for {company['name']}: {str(e)}")
            
            enriched_companies.append(company)
        
        return enriched_companies

class EmailGenerator:
    def __init__(self):
        self.templates = {
            'initial_outreach': (
                "Subject: Partnership Opportunity with {project_name}\n\n"
                "Dear {company_name} Team,\n\n"
                "I hope this email finds you well. My name is {user_name} and I am reaching out regarding a potential sponsorship opportunity for {project_name}.\n\n"
                "{project_description}\n\n"
                "Based on {company_name}'s commitment to {industry}, I believe there could be a valuable partnership opportunity here that aligns with your brand values and goals.\n\n"
                "Here's how this collaboration could benefit {company_name}:\n"
                "- Increased visibility among {target_audience}\n"
                "- Association with an initiative that promotes {benefit}\n"
                "- Opportunity to showcase your brand's commitment to {value}\n\n"
                "Would you be interested in discussing this opportunity further? I'd be happy to provide additional details about our sponsorship packages and the specific benefits each offers.\n\n"
                "Thank you for considering this partnership. I look forward to your response.\n\n"
                "Best regards,\n"
                "{user_name}\n"
                "{user_contact}"
            ),
            'followup': (
                "Subject: Following Up: Partnership Opportunity with {project_name}\n\n"
                "Dear {company_name} Team,\n\n"
                "I hope this email finds you well. I wanted to follow up on my previous email regarding a potential sponsorship opportunity for {project_name}.\n\n"
                "I understand that you might be busy, but I'd still love to discuss how a partnership could benefit both {company_name} and our initiative.\n\n"
                "If you're interested, I'd be happy to schedule a brief call to provide more details about:\n"
                "- Our sponsorship packages\n"
                "- The specific audience reach\n"
                "- The promotional opportunities available\n\n"
                "Please let me know if you have any questions or if there's a better time to connect.\n\n"
                "Best regards,\n"
                "{user_name}\n"
                "{user_contact}"
            )
        }
    
    def generate_email(self, template_name, **kwargs):
        """Generate email from template with provided variables."""
        if template_name not in self.templates:
            return None, None
        
        template = self.templates[template_name]
        
        # Split subject and body
        subject_body = template.split("\n\n", 1)
        subject = subject_body[0].replace("Subject: ", "").format(**kwargs)
        body = subject_body[1].format(**kwargs)
        
        return subject, body
    
    def add_template(self, name, template):
        """Add a new email template."""
        self.templates[name] = template
        return True

class SponsorshipOutreachAgent:
    def __init__(self, serp_api_key=None):
        self.gmail = GmailAPI()
        self.db = SponsorshipDatabase()
        self.finder = SponsorFinder(serp_api_key)
        self.email_gen = EmailGenerator()
        self.user_info = {}
    
    def setup_user_info(self):
        """Collect user information for email templates."""
        print("\n=== User Information Setup ===")
        print("This information will be used in your outreach emails.")
        
        self.user_info['name'] = input("Your name: ")
        self.user_info['email'] = input("Your email address: ")
        self.user_info['phone'] = input("Your phone number (optional): ")
        
        contact = self.user_info['email']
        if self.user_info['phone']:
            contact += f" | {self.user_info['phone']}"
        
        self.user_info['contact'] = contact
        return self.user_info
    
    def create_project(self):
        """Create a new sponsorship project."""
        print("\n=== Create New Sponsorship Project ===")
        
        project = {
            'name': input("Project name: "),
            'description': input("Project description (be detailed): "),
            'requirements': input("Sponsorship requirements (funding, resources, etc.): "),
            'target_audience': input("Target audience: "),
            'budget': input("Budget goal (optional): "),
            'timeline': input("Project timeline: ")
        }
        
        # Add project to database
        project_id = self.db.add_project(
            project['name'], 
            project['description'],
            project['requirements'],
            project['target_audience'],
            project['budget'],
            project['timeline']
        )
        
        if project_id:
            print(f"\nProject '{project['name']}' created successfully with ID: {project_id}")
            return project_id
        else:
            print("\nError creating project. Please try again.")
            return None
    
    def find_potential_sponsors(self, project_id, limit=20):
        """Find potential sponsors for a project."""
        project = self.db.get_project(project_id)
        if not project:
            print("Project not found.")
            return []
        
        print(f"\n=== Finding Sponsors for {project['name']} ===")
        print("Searching for potential sponsors. This may take a few minutes...")
        
        # Extract keywords from project description
        keywords = project['description'].split()[:5]
        industry = input("Enter industry keywords to target (e.g., tech, education): ")
        
        # Search for sponsors
        companies = self.finder.search_sponsors(
            project['description'], 
            industry=industry,
            limit=limit
        )
        
        # Enrich company data
        companies = self.finder.enrich_company_data(companies)
        
        # Store companies in database
        for company in companies:
            company_id = self.db.add_company(
                name=company['name'],
                email=company.get('email'),
                website=company.get('website'),
                email=company.get('email'),
                website=company.get('website'),
                industry=industry,
                description=company.get('description'),
                source=company.get('source'),
                relevance_score=company.get('relevance_score', 0.5)
            )
        
        print(f"\nFound {len(companies)} potential sponsors!")
        return companies
    
    def generate_outreach_emails(self, project_id):
        """Generate outreach emails for a project."""
        project = self.db.get_project(project_id)
        if not project:
            print("Project not found.")
            return False
        
        print(f"\n=== Generating Outreach Emails for {project['name']} ===")
        
        # Get companies for outreach
        companies = self.db.get_companies_for_outreach(limit=20)
        if not companies:
            print("No companies found for outreach.")
            return False
        
        # Check if user info is set
        if not self.user_info:
            self.setup_user_info()
        
        # Generate and store emails
        email_count = 0
        for company in companies:
            company_id, name, email, website, industry, score = company
            
            if not email:
                print(f"Skipping {name} - No email address available")
                continue
            
            try:
                # Generate personalized email
                subject, body = self.email_gen.generate_email(
                    'initial_outreach',
                    project_name=project['name'],
                    project_description=project['description'],
                    company_name=name,
                    industry=industry or "your industry",
                    target_audience=project['target_audience'] or "our target audience",
                    benefit="innovation and community engagement",
                    value="excellence and community support",
                    user_name=self.user_info['name'],
                    user_contact=self.user_info['contact']
                )
                
                if subject and body:
                    # Add to outreach database
                    outreach_id = self.db.add_outreach(company_id, subject, body)
                    if outreach_id:
                        email_count += 1
                        print(f"Generated email for {name}")
            except Exception as e:
                print(f"Error generating email for {name}: {str(e)}")
        
        print(f"\nGenerated {email_count} outreach emails!")
        return True
    
    def send_outreach_emails(self, project_id, batch_size=5, confirm_each=False):
        """Send generated outreach emails."""
        project = self.db.get_project(project_id)
        if not project:
            print("Project not found.")
            return False
        
        print(f"\n=== Sending Outreach Emails for {project['name']} ===")
        
        # Get pending outreach emails
        cursor = self.db.conn.cursor()
        cursor.execute('''
        SELECT o.id, c.name, c.email, o.email_subject, o.email_body
        FROM outreach o
        JOIN companies c ON o.company_id = c.id
        WHERE o.status='pending' AND c.email IS NOT NULL
        ''')
        
        outreach_emails = cursor.fetchall()
        
        if not outreach_emails:
            print("No pending outreach emails found.")
            return False
        
        print(f"Found {len(outreach_emails)} pending outreach emails.")
        
        if not confirm_each:
            confirm = input(f"Send {min(batch_size, len(outreach_emails))} emails now? (yes/no): ")
            if confirm.lower() != 'yes':
                print("Sending cancelled.")
                return False
        
        # Send emails in batches
        sent_count = 0
        for i, (outreach_id, company_name, email, subject, body) in enumerate(outreach_emails):
            if i >= batch_size:
                break
            
            if confirm_each:
                print(f"\nPreparing to send email to {company_name} ({email}):")
                print(f"Subject: {subject}")
                confirm = input("Send this email? (yes/no): ")
                if confirm.lower() != 'yes':
                    print("Skipping this email.")
                    continue
            
            # Send email
            result = self.gmail.send_message(email, subject, body, auto_mode=not confirm_each)
            
            if "sent successfully" in result:
                self.db.update_outreach_status(outreach_id, "sent")
                sent_count += 1
                print(f"Sent email to {company_name} ({email})")
            else:
                print(f"Failed to send email to {company_name}: {result}")
            
            # Add delay between sends
            time.sleep(random.uniform(1, 3))
        
        print(f"\nSent {sent_count} outreach emails!")
        return True
    
    def check_responses(self, project_id=None):
        """Check for responses to outreach emails."""
        print("\n=== Checking for Responses ===")
        
        # Construct query
        query = "sponsorship partnership"
        
        # Get responses from Gmail
        responses = self.gmail.check_for_responses(query, days=14)
        
        if isinstance(responses, str):
            print(responses)
            return False
        
        if not responses:
            print("No new responses found.")
            return False
        
        print(f"Found {len(responses)} potential responses!")
        
        # Process each response
        for response in responses:
            sender = response['from']
            subject = response['subject']
            print(f"\nFrom: {sender}")
            print(f"Subject: {subject}")
            print(f"Snippet: {response['snippet']}")
            
            # Extract company name from email
            company_name = sender.split('<')[0].strip()
            
            # Check if this is related to one of our outreach attempts
            cursor = self.db.conn.cursor()
            cursor.execute('''
            SELECT o.id, c.id, c.name, o.email_subject
            FROM outreach o
            JOIN companies c ON o.company_id = c.id
            WHERE c.name LIKE ? OR ? LIKE CONCAT('%', c.name, '%')
            ''', (f"%{company_name}%", sender))
            
            outreach = cursor.fetchone()
            
            if outreach:
                outreach_id, company_id, db_company_name, outreach_subject = outreach
                print(f"This appears to be a response to our outreach to {db_company_name}!")
                
                # Get full message
                message = self.gmail.get_message(response['id'])
                if not isinstance(message, str):
                    # Update outreach status
                    self.db.update_outreach_status(
                        outreach_id, 
                        "responded", 
                        response_content=message['body']
                    )
                    print("Recorded response in database.")
                else:
                    print(f"Error retrieving full message: {message}")
            else:
                print("This does not match any of our outreach attempts.")
        
        return True
    
    def generate_followups(self):
        """Generate follow-up emails for outreach with no response."""
        print("\n=== Generating Follow-up Emails ===")
        
        # Get pending followups
        followups = self.db.get_pending_followups(days_since_sent=7)
        
        if not followups:
            print("No follow-ups needed at this time.")
            return False
        
        print(f"Found {len(followups)} outreach attempts that need follow-up.")
        
        # Generate and send followups
        for outreach_id, company_name, email, subject in followups:
            if not email:
                continue
            
            # Get project details
            cursor = self.db.conn.cursor()
            cursor.execute('''
            SELECT p.name, p.description
            FROM outreach o
            JOIN companies c ON o.company_id = c.id
            JOIN projects p ON p.id = 1  # Assuming project ID connection would exist
            WHERE o.id = ?
            ''', (outreach_id,))
            
            project = cursor.fetchone()
            if not project:
                project = ("Our Project", "")  # Fallback if project not found
            
            project_name, project_description = project
            
            # Generate follow-up email
            subject, body = self.email_gen.generate_email(
                'followup',
                project_name=project_name,
                company_name=company_name,
                user_name=self.user_info.get('name', 'Me'),
                user_contact=self.user_info.get('contact', '')
            )
            
            print(f"\nGenerated follow-up for {company_name}")
            print(f"Subject: {subject}")
            
            confirm = input("\nSend this follow-up? (yes/no): ")
            if confirm.lower() == 'yes':
                # Send email
                result = self.gmail.send_message(email, subject, body)
                
                if "sent successfully" in result:
                    self.db.update_outreach_status(outreach_id, "followup_sent")
                    print(f"Sent follow-up email to {company_name}")
                else:
                    print(f"Failed to send follow-up to {company_name}: {result}")
            else:
                print("Skipping this follow-up.")
            
            # Add delay between sends
            time.sleep(random.uniform(1, 2))
        
        return True
    
    def show_stats(self):
        """Show sponsorship outreach statistics."""
        print("\n=== Sponsorship Outreach Statistics ===")
        
        cursor = self.db.conn.cursor()
        
        # Total companies
        cursor.execute("SELECT COUNT(*) FROM companies")
        total_companies = cursor.fetchone()[0]
        
        # Total outreach attempts
        cursor.execute("SELECT COUNT(*) FROM outreach")
        total_outreach = cursor.fetchone()[0]
        
        # Response rate
        cursor.execute("SELECT COUNT(*) FROM outreach WHERE response_received=1")
        responses = cursor.fetchone()[0]
        
        response_rate = (responses / total_outreach * 100) if total_outreach > 0 else 0
        
        # Status breakdown
        cursor.execute('''
        SELECT status, COUNT(*) 
        FROM outreach 
        GROUP BY status
        ''')
        status_breakdown = cursor.fetchall()
        
        print(f"Total Companies in Database: {total_companies}")
        print(f"Total Outreach Attempts: {total_outreach}")
        print(f"Response Rate: {response_rate:.1f}%")
        
        print("\nStatus Breakdown:")
        for status, count in status_breakdown:
            print(f"  {status}: {count}")
        
        return True
    
    def export_data(self):
        """Export data to CSV files."""
        print("\n=== Export Data to CSV ===")
        print("1. Export Companies")
        print("2. Export Outreach")
        print("3. Export Projects")
        print("4. Export All")
        
        choice = input("\nEnter your choice (1-4): ")
        
        if choice == '1':
            filename = self.db.export_to_csv('companies')
            if filename:
                print(f"Companies exported to {filename}")
        elif choice == '2':
            filename = self.db.export_to_csv('outreach')
            if filename:
                print(f"Outreach data exported to {filename}")
        elif choice == '3':
            filename = self.db.export_to_csv('projects')
            if filename:
                print(f"Projects exported to {filename}")
        elif choice == '4':
            for table in ['companies', 'outreach', 'projects']:
                filename = self.db.export_to_csv(table)
                if filename:
                    print(f"{table.capitalize()} exported to {filename}")
        else:
            print("Invalid choice")
        
        return True
    
    def cleanup(self):
        """Clean up database connections."""
        self.db.close()
        print("Cleaned up resources.")

def main():
    print("=== Sponsorship Outreach Agent ===")
    print("This tool helps automate sponsorship outreach for your projects")
    print("======================================")
    
    # Check for SerpAPI key
    serp_api_key = None
    if os.path.exists('serpapi_key.txt'):
        with open('serpapi_key.txt', 'r') as f:
            serp_api_key = f.read().strip()
    else:
        print("SerpAPI key not found. You can get one at https://serpapi.com/")
        print("For better search results, save your key in 'serpapi_key.txt'")
        print("Using basic search instead (less accurate but no API key needed).\n")
    
    agent = SponsorshipOutreachAgent(serp_api_key)
    
    # Collect user info for email templates
    agent.setup_user_info()
    
    while True:
        print("\nMain Options:")
        print("1. Create New Sponsorship Project")
        print("2. Manage Existing Project")
        print("3. View Gmail Messages")
        print("4. Send Manual Email")
        print("5. Show Statistics")
        print("6. Export Data")
        print("7. Exit")
        
        choice = input("\nEnter your choice (1-7): ")
        
        if choice == '1':
            project_id = agent.create_project()
            if project_id:
                # Continue with workflow for new project
                agent.find_potential_sponsors(project_id)
                agent.generate_outreach_emails(project_id)
                
                send_now = input("\nWould you like to send emails now? (yes/no): ")
                if send_now.lower() == 'yes':
                    agent.send_outreach_emails(project_id)
        
        elif choice == '2':
            # Show list of existing projects
            projects = agent.db.get_all_projects()
            
            if not projects:
                print("No projects found. Please create a project first.")
                continue
            
            print("\nExisting Projects:")
            for i, (proj_id, name, desc) in enumerate(projects):
                print(f"{i+1}. {name} (ID: {proj_id})")
                print(f"   {desc[:50]}..." if desc and len(desc) > 50 else "")
            
            project_choice = input("\nSelect project number or 'b' to go back: ")
            if project_choice.lower() == 'b':
                continue
            
            try:
                project_index = int(project_choice) - 1
                project_id = projects[project_index][0]
                
                # Project management submenu
                while True:
                    print("\nProject Management:")
                    print("1. Find More Potential Sponsors")
                    print("2. Generate Outreach Emails")
                    print("3. Send Outreach Emails")
                    print("4. Check for Responses")
                    print("5. Generate Follow-ups")
                    print("6. Back to Main Menu")
                    
                    sub_choice = input("\nEnter your choice (1-6): ")
                    
                    if sub_choice == '1':
                        agent.find_potential_sponsors(project_id)
                    elif sub_choice == '2':
                        agent.generate_outreach_emails(project_id)
                    elif sub_choice == '3':
                        agent.send_outreach_emails(project_id)
                    elif sub_choice == '4':
                        agent.check_responses(project_id)
                    elif sub_choice == '5':
                        agent.generate_followups()
                    elif sub_choice == '6':
                        break
                    else:
                        print("Invalid choice. Please try again.")
            
            except (ValueError, IndexError):
                print("Invalid selection. Please try again.")
        
        elif choice == '3':
            # Gmail inbox view similar to original code
            gmail = GmailAPI()
            
            while True:
                print("\nGmail Options:")
                print("1. List recent emails")
                print("2. Read a specific email")
                print("3. Back to Main Menu")
                
                gmail_choice = input("\nEnter your choice (1-3): ")
                
                if gmail_choice == '1':
                    max_results = int(input("How many emails to list? (default 10): ") or 10)
                    query = input("Search query (optional): ") or None
                    messages = gmail.list_messages(max_results, query)
                    
                    if isinstance(messages, str):
                        print(messages)
                    else:
                        print("\nRecent emails:")
                        for i, msg in enumerate(messages):
                            print(f"{i+1}. From: {msg['from']}")
                            print(f"   Subject: {msg['subject']}")
                            print(f"   Date: {msg['date']}")
                            print(f"   Snippet: {msg['snippet']}")
                            print(f"   ID: {msg['id']}")
                            print()
                
                elif gmail_choice == '2':
                    message_id = input("Enter the message ID: ")
                    message = gmail.get_message(message_id)
                    
                    if isinstance(message, str):
                        print(message)
                    else:
                        print("\nEmail details:")
                        print(f"From: {message['from']}")
                        print(f"Subject: {message['subject']}")
                        print(f"Date: {message['date']}")
                        print("\nBody:")
                        print(message['body'])
                
                elif gmail_choice == '3':
                    break
                
                else:
                    print("Invalid choice. Please try again.")
        
        elif choice == '4':
            # Manual email sending (from original code)
            gmail = GmailAPI()
            
            to = input("To: ")
            subject = input("Subject: ")
            print("Body (type END on a new line to finish):")
            body_lines = []
            while True:
                line = input()
                if line == "END":
                    break
                body_lines.append(line)
            body = "\n".join(body_lines)
            
            result = gmail.send_message(to, subject, body)
            print(result)
        
        elif choice == '5':
            agent.show_stats()
        
        elif choice == '6':
            agent.export_data()
        
        elif choice == '7':
            agent.cleanup()
            print("Goodbye!")
            break
        
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main()