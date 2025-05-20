#!/usr/bin/env python3
import os
import datetime
import sys
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
import json
import contextlib
from datetime import datetime, timedelta
import sqlalchemy
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, MetaData, Table, select, func, and_
from sqlalchemy.dialects.postgresql import JSONB
import logfire

from pydantic import BaseModel, Field
from pydantic_ai import AI, ImageQuery, MCPToolRunPython
from pydantic_ai.input.image import Image

# Configure logging
logfire.configure(level="INFO")
logger = logfire.getLogger("receipt_agent")

# Database configuration
DB_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@postgres:5432/postgres")

# Define database schema
DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS receipts (
    id SERIAL PRIMARY KEY,
    store_name TEXT,
    date TIMESTAMP,
    total FLOAT,
    items JSONB,
    receipt_image_path TEXT,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# Pydantic models for data validation
class ReceiptItem(BaseModel):
    name: str
    price: float
    quantity: Optional[float] = 1.0
    category: Optional[str] = None

class Receipt(BaseModel):
    store_name: str
    date: datetime
    total: float
    items: List[ReceiptItem]
    receipt_image_path: str

class AnalysisRequest(BaseModel):
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    category: Optional[str] = None
    store: Optional[str] = None
    search_term: Optional[str] = None

class AnalysisResult(BaseModel):
    total_amount: float
    item_count: int
    period: str
    breakdown: Dict[str, float] = {}
    additional_info: Optional[Dict[str, Any]] = None

class ReceiptAgent:
    def __init__(self):
        """Initialize the receipt processing agent."""
        self.engine = create_engine(DB_URL)
        self.setup_database()
        self.receipt_folder = Path("receipts")
        self.receipt_folder.mkdir(exist_ok=True)
        
        # Configure the AI model
        self.ai = AI(
            model="anthropic/claude-3-haiku-20240307",
            tools=[MCPToolRunPython()]
        )

    def setup_database(self):
        """Set up the database tables if they don't exist."""
        try:
            with self.engine.connect() as conn:
                conn.execute(sqlalchemy.text(DB_SCHEMA))
                conn.commit()
                logger.info("Database setup complete")
        except Exception as e:
            logger.error(f"Database setup failed: {e}")
            sys.exit(1)
    
    def get_recent_receipts(self, days: int = 1) -> List[Path]:
        """Find receipt images added within the specified number of days."""
        cutoff_time = datetime.now() - timedelta(days=days)
        image_extensions = {'.jpg', '.jpeg', '.png', '.webp', '.heic', '.heif'}
        
        recent_files = []
        for file_path in self.receipt_folder.glob('**/*'):
            if (file_path.is_file() and 
                file_path.suffix.lower() in image_extensions and 
                datetime.fromtimestamp(file_path.stat().st_mtime) > cutoff_time):
                recent_files.append(file_path)
        
        return recent_files

    async def process_receipt_image(self, image_path: Path) -> Optional[Receipt]:
        """Process a single receipt image and extract structured data."""
        try:
            logger.info(f"Processing receipt image: {image_path}")
            
            # Load the image
            image = Image.from_file(image_path)
            
            # Extract data using AI
            response = await self.ai.extract(
                """
                Extract all available information from this receipt image into a structured format.
                
                I need the following details:
                1. Store name
                2. Date (in YYYY-MM-DD format)
                3. Total amount
                4. List of items purchased with:
                   - Item name
                   - Price
                   - Quantity (if available)
                   - Category (if you can determine it)
                
                For items, please try to categorize them into general categories like:
                "groceries", "food", "beverages", "household", "electronics", "clothing", etc.
                
                Be precise with the extraction and make reasonable assumptions if some information is partially visible.
                """,
                image=ImageQuery(image=image),
                output_type=Receipt,
                output_kwargs={"receipt_image_path": str(image_path)}
            )
            
            logger.info(f"Successfully extracted data from receipt: {image_path}")
            return response
        
        except Exception as e:
            logger.error(f"Failed to process receipt {image_path}: {e}")
            return None
    
    def save_receipt_to_db(self, receipt: Receipt) -> bool:
        """Save the processed receipt data to the database."""
        try:
            metadata = MetaData()
            receipts_table = Table('receipts', metadata, autoload_with=self.engine)
            
            # Convert items to JSON serializable format
            items_json = [item.model_dump() for item in receipt.items]
            
            # Insert into database
            with self.engine.begin() as conn:
                conn.execute(
                    receipts_table.insert().values(
                        store_name=receipt.store_name,
                        date=receipt.date,
                        total=receipt.total,
                        items=items_json,
                        receipt_image_path=receipt.receipt_image_path,
                        processed_at=datetime.now()
                    )
                )
            
            logger.info(f"Receipt saved to database: {receipt.store_name}, {receipt.date}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to save receipt to database: {e}")
            return False
    
    async def process_recent_receipts(self, days: int = 1) -> Dict[str, Any]:
        """Process all receipt images added within the specified number of days."""
        receipt_images = self.get_recent_receipts(days)
        
        if not receipt_images:
            return {"status": "No recent receipt images found", "count": 0}
        
        results = {
            "status": "Processing complete",
            "processed": 0,
            "failed": 0,
            "receipt_details": []
        }
        
        for image_path in receipt_images:
            receipt = await self.process_receipt_image(image_path)
            
            if receipt:
                if self.save_receipt_to_db(receipt):
                    results["processed"] += 1
                    results["receipt_details"].append({
                        "store": receipt.store_name,
                        "date": receipt.date.isoformat(),
                        "total": receipt.total,
                        "items_count": len(receipt.items)
                    })
                else:
                    results["failed"] += 1
            else:
                results["failed"] += 1
        
        return results
    
    async def analyze_spending(self, request: AnalysisRequest) -> AnalysisResult:
        """Analyze spending data based on the provided criteria."""
        # Create a tool execution context for running Python code
        tool = MCPToolRunPython()
        
        # Prepare necessary data
        analysis_code = f"""
import sqlalchemy
from sqlalchemy import create_engine, MetaData, Table, select, func, and_
import json
from datetime import datetime
import pandas as pd

# Connect to the database
engine = create_engine("{DB_URL}")
metadata = MetaData()
receipts_table = Table('receipts', metadata, autoload_with=engine)

# Build the query based on the filters
query = select([
    receipts_table.c.id,
    receipts_table.c.store_name,
    receipts_table.c.date,
    receipts_table.c.total,
    receipts_table.c.items
])

# Apply filters
filters = []
if {repr(request.start_date)}:
    filters.append(receipts_table.c.date >= {repr(request.start_date)})
if {repr(request.end_date)}:
    filters.append(receipts_table.c.date <= {repr(request.end_date)})
if {repr(request.store)}:
    filters.append(receipts_table.c.store_name.ilike(f"%{str(request.store)}%"))

# Execute query with filters
if filters:
    query = query.where(and_(*filters))

# Execute the query
with engine.connect() as conn:
    result = conn.execute(query)
    rows = result.fetchall()

# Process the data
total_amount = 0
item_count = 0
store_breakdown = {{}}
category_breakdown = {{}}
item_breakdown = {{}}

# Handle the search term filter in Python
search_term = {repr(request.search_term)}
search_term = search_term.lower() if search_term else None

for row in rows:
    row_dict = dict(row)
    items = row_dict['items']
    
    # For each receipt, process its items
    for item in items:
        # Convert string to dict if needed
        if isinstance(item, str):
            item = json.loads(item)
        
        item_name = item.get('name', '').lower()
        item_price = float(item.get('price', 0))
        item_quantity = float(item.get('quantity', 1))
        item_category = item.get('category', 'uncategorized').lower()
        
        # Apply search term filter if provided
        if search_term and search_term not in item_name and search_term not in item_category:
            continue
            
        # Update totals
        total_amount += item_price * item_quantity
        item_count += item_quantity
        
        # Update breakdowns
        store_name = row_dict['store_name']
        store_breakdown[store_name] = store_breakdown.get(store_name, 0) + (item_price * item_quantity)
        category_breakdown[item_category] = category_breakdown.get(item_category, 0) + (item_price * item_quantity)
        item_breakdown[item_name] = item_breakdown.get(item_name, 0) + (item_price * item_quantity)

# Determine the period description
if {repr(request.start_date)} and {repr(request.end_date)}:
    period = f"from {request.start_date.strftime('%Y-%m-%d')} to {request.end_date.strftime('%Y-%m-%d')}"
elif {repr(request.start_date)}:
    period = f"since {request.start_date.strftime('%Y-%m-%d')}"
elif {repr(request.end_date)}:
    period = f"until {request.end_date.strftime('%Y-%m-%d')}"
else:
    period = "all time"

# Create the result JSON
result = {{
    "total_amount": round(total_amount, 2),
    "item_count": int(item_count),
    "period": period,
    "breakdown": {{
        "by_store": {{}},
        "by_category": {{}},
        "by_item": {{}}
    }},
    "additional_info": {{
        "receipt_count": len(rows),
        "date_range": {{
            "min": min([row['date'] for row in rows]).strftime('%Y-%m-%d') if rows else "N/A",
            "max": max([row['date'] for row in rows]).strftime('%Y-%m-%d') if rows else "N/A"
        }}
    }}
}}

# Add top 5 entries for each breakdown
for store, amount in sorted(store_breakdown.items(), key=lambda x: x[1], reverse=True)[:5]:
    result["breakdown"]["by_store"][store] = round(amount, 2)
    
for category, amount in sorted(category_breakdown.items(), key=lambda x: x[1], reverse=True)[:5]:
    result["breakdown"]["by_category"][category] = round(amount, 2)
    
for item, amount in sorted(item_breakdown.items(), key=lambda x: x[1], reverse=True)[:5]:
    result["breakdown"]["by_item"][item] = round(amount, 2)

print(json.dumps(result, default=str))
"""

        # Execute the analysis
        try:
            code_result = await tool.run(analysis_code)
            analysis_data = json.loads(code_result.stdout)
            
            # Format the result using our Pydantic model
            return AnalysisResult(
                total_amount=analysis_data["total_amount"],
                item_count=analysis_data["item_count"],
                period=analysis_data["period"],
                breakdown={
                    "by_store": analysis_data["breakdown"]["by_store"],
                    "by_category": analysis_data["breakdown"]["by_category"],
                    "by_item": analysis_data["breakdown"]["by_item"]
                },
                additional_info=analysis_data["additional_info"]
            )
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            # Return a minimal result with error information
            return AnalysisResult(
                total_amount=0,
                item_count=0,
                period="error",
                breakdown={},
                additional_info={"error": str(e)}
            )

    async def run_cli(self):
        """Run the CLI interface for the receipt agent."""
        if len(sys.argv) < 2:
            print("""
Receipt Processing Agent - Commands:
    process [days=1]     - Process receipts from the last N days
    analyze              - Analyze spending (interactive mode)
    help                 - Show this help message
            """)
            return
        
        command = sys.argv[1].lower()
        
        if command == "process":
            days = 1
            if len(sys.argv) > 2:
                try:
                    days = int(sys.argv[2])
                except ValueError:
                    print("Error: Days must be a number.")
                    return
            
            print(f"Processing receipts from the last {days} day(s)...")
            results = await self.process_recent_receipts(days)
            print(json.dumps(results, indent=2, default=str))
            
        elif command == "analyze":
            print("Spending Analysis - Interactive Mode")
            print("Press Enter to skip any filter")
            
            # Get user input for analysis parameters
            start_date_str = input("Start date (YYYY-MM-DD): ").strip()
            end_date_str = input("End date (YYYY-MM-DD): ").strip()
            store = input("Store name (partial match): ").strip() or None
            category = input("Category (partial match): ").strip() or None
            search_term = input("Search term (item name): ").strip() or None
            
            # Parse dates
            start_date = None
            end_date = None
            try:
                if start_date_str:
                    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
                if end_date_str:
                    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
            except ValueError:
                print("Error: Invalid date format. Use YYYY-MM-DD.")
                return
            
            # Create analysis request
            request = AnalysisRequest(
                start_date=start_date,
                end_date=end_date,
                store=store,
                category=category,
                search_term=search_term
            )
            
            print("\nRunning analysis...")
            result = await self.analyze_spending(request)
            
            # Print analysis results in a readable format
            print("\n----- Analysis Results -----")
            print(f"Period: {result.period}")
            print(f"Total amount: ${result.total_amount:.2f}")
            print(f"Item count: {result.item_count}")
            
            if "by_store" in result.breakdown:
                print("\nTop stores by spending:")
                for store, amount in result.breakdown["by_store"].items():
                    print(f"  {store}: ${amount:.2f}")
            
            if "by_category" in result.breakdown:
                print("\nTop categories by spending:")
                for category, amount in result.breakdown["by_category"].items():
                    print(f"  {category}: ${amount:.2f}")
            
            if "by_item" in result.breakdown:
                print("\nTop items by spending:")
                for item, amount in result.breakdown["by_item"].items():
                    print(f"  {item}: ${amount:.2f}")
            
            if result.additional_info:
                print("\nAdditional information:")
                for key, value in result.additional_info.items():
                    print(f"  {key}: {value}")
        
        elif command == "help":
            print("""
Receipt Processing Agent - Commands:
    process [days=1]     - Process receipts from the last N days
    analyze              - Analyze spending (interactive mode)
    help                 - Show this help message
            """)
        
        else:
            print(f"Unknown command: {command}")
            print("Use 'help' to see available commands.")


async def main():
    """Main entry point for the receipt agent."""
    agent = ReceiptAgent()
    await agent.run_cli()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())