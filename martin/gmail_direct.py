import os
import json
import base64
import sys
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Check if required packages are installed
required_packages = ['google-auth', 'google-auth-oauthlib', 'google-api-python-client']
try:
    import google.auth
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
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

# Gmail API setup
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly', 
          'https://www.googleapis.com/auth/gmail.send']

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
    
    def send_message(self, to, subject, body):
        """Send an email message."""
        try:
            message = MIMEMultipart()
            message['to'] = to
            message['subject'] = subject
            
            msg = MIMEText(body)
            message.attach(msg)
            
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
            
            # Confirm before sending
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

def main():
    print("=== Gmail API Direct Access ===")
    print("This script allows you to interact directly with the Gmail API")
    print("==================================")
    
    gmail = GmailAPI()
    
    while True:
        print("\nOptions:")
        print("1. List recent emails")
        print("2. Read a specific email")
        print("3. Send an email")
        print("4. Exit")
        
        choice = input("\nEnter your choice (1-4): ")
        
        if choice == '1':
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
        
        elif choice == '2':
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
        
        elif choice == '3':
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
        
        elif choice == '4':
            print("Goodbye!")
            break
        
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main()