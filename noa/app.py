import asyncio
import os
import sys
import io
import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, Union, Tuple

import logfire
from pydantic import BaseModel
from pydantic_ai import Agent, BinaryContent
from pydantic_ai.mcp import MCPServerStdio
from pydantic_ai.models.groq import GroqModel
from pydantic_ai.providers.groq import GroqProvider

# OCR imports
import pytesseract
from pdf2image import convert_from_path
from PIL import Image as PILImage

from noa.analysis import analyze_spending, get_spending_for_period
from noa.db import init_db, save_receipt, get_receipts
from noa.models import Receipt, ReceiptItem, ReceiptOCRResult, SpendingAnalysis

# Configure logging
logfire.configure()
Agent.instrument_all()

# Helper function to extract JSON from text
def extract_json_from_text(text: str) -> str:
    """
    Extract JSON from text that may contain other content.

    Args:
        text: Text that may contain JSON

    Returns:
        Extracted JSON string or empty string if no JSON found
    """
    # Try to find JSON between triple backticks
    json_pattern = r"```(?:json)?\s*([\s\S]*?)```"
    matches = re.findall(json_pattern, text)

    if matches:
        return matches[0].strip()

    # Try to find JSON between curly braces
    json_pattern = r"\{[\s\S]*\}"
    matches = re.findall(json_pattern, text)

    if matches:
        # Find the largest match (most likely to be the complete JSON)
        return max(matches, key=len)

    return ""

ROOT_DIR = Path("noa/receipts").resolve()

# Set up the model
llm_model = GroqModel(
    'meta-llama/llama-4-maverick-17b-128e-instruct',
    provider=GroqProvider(api_key=os.getenv('GROQ_API_KEY'))
)

# Set up MCP servers
mcp_servers = [
    MCPServerStdio("npx", ["-y", "@modelcontextprotocol/server-filesystem", ROOT_DIR.as_posix()]),
    MCPServerStdio('npx', ['-y', '@pydantic/mcp-run-python', 'stdio']),
]

# Print MCP server configuration for debugging
print(f"MCP Filesystem server path: {ROOT_DIR.as_posix()}")
print(f"MCP servers configured: {len(mcp_servers)}")

# Create the agent
agent = Agent(
    model=llm_model,
    mcp_servers=mcp_servers,
    instructions="""
    You are a receipt processing assistant. You can:
    1. Process receipt images to extract data
    2. Save receipt data to a database
    3. Analyze spending patterns

    When processing receipts, extract the following information:
    - Store name
    - Date of purchase
    - Total amount
    - Individual items with prices and quantities
    - Payment method (if available)
    - Tax amount (if available)

    For spending analysis, you can answer questions like:
    - How much did I spend last month?
    - What's my spending by category?
    - How much did I spend at a specific store?

    If you're missing any information needed for analysis, ask the user.
    """
)


def perform_ocr(image_path: str) -> str:
    """
    Perform OCR on an image file to extract text.

    Args:
        image_path: Path to the image file

    Returns:
        Extracted text from the image
    """
    path = Path(image_path)
    text_content = ""

    try:
        if path.suffix.lower() == '.pdf':
            # Convert PDF to images
            images = convert_from_path(image_path)
            for img in images:
                text_content += pytesseract.image_to_string(img) + "\n\n"
        else:
            # Process image file directly
            img = PILImage.open(path)
            text_content = pytesseract.image_to_string(img)

        return text_content
    except Exception as e:
        logfire.error(f"OCR failed: {str(e)}")
        return ""


async def process_receipt_image(image_path: str) -> ReceiptOCRResult:
    """
    Process a receipt image and extract data using OCR.

    Args:
        image_path: Path to the receipt image

    Returns:
        ReceiptOCRResult with the extracted data or error message
    """
    try:
        # Step 1: Perform OCR to extract text
        ocr_text = perform_ocr(image_path)

        # Use the run_mcp_servers context manager to ensure MCP servers are running
        async with agent.run_mcp_servers():
            if not ocr_text.strip():
                # If OCR failed to extract any text, fall back to using the LLM directly with the image
                image_data = Path(image_path).read_bytes()

                # Create a prompt for the OCR task
                prompt = [
                    """Extract all information from this receipt image. Include:
                    1. Store name (required)
                    2. Date of purchase (required, in format YYYY-MM-DD)
                    3. Total amount (required, as a number without currency symbol)
                    4. List of items with prices and quantities (if available)
                    5. Payment method (if available)
                    6. Tax amount (if available, as a number without currency symbol)

                    Format your response as a structured list with clear labels, not as JSON.
                    """,
                    BinaryContent(data=image_data, media_type="image/jpeg")
                ]

                # Run the agent to extract data
                result = await agent.run(prompt)
                extracted_text = result.output
            else:
                # Use the OCR text
                extracted_text = ocr_text

                # Enhance OCR results with the LLM
                prompt = f"""
                I have performed OCR on a receipt image and got the following text:

                {ocr_text}

                Please extract the following information in a structured format:
                1. Store name (required)
                2. Date of purchase (required, in format YYYY-MM-DD)
                3. Total amount (required, as a number without currency symbol)
                4. List of items with prices and quantities (if available)
                5. Payment method (if available)
                6. Tax amount (if available, as a number without currency symbol)

                If some information is unclear or missing but required, make reasonable assumptions based on the available text.
                For example, if the store name is unclear, use the most prominent text at the top of the receipt.
                If the date is unclear, use today's date.
                If the total amount is unclear, sum up the prices of the items if possible.

                Format your response as a structured list with clear labels, not as JSON.
                """

                # Run the agent to extract structured data from OCR text
                result = await agent.run(prompt)
                extracted_text = result.output

            # Parse the extracted data into a Receipt object
            receipt_data = await agent.run(
                f"""Convert the following receipt data into a structured JSON format that matches the Receipt model:

{extracted_text}

The JSON must include these required fields:
- store_name: string
- date: string in ISO format (e.g., "2023-12-15T14:30:00")
- total_amount: number
- items: array of objects with name, price, and quantity

Example format:
```json
{{
  "store_name": "GROCERY STORE",
  "date": "2023-12-15T14:30:00",
  "total_amount": 34.69,
  "items": [
    {{ "name": "Milk", "price": 3.99, "quantity": 1 }},
    {{ "name": "Bread", "price": 2.49, "quantity": 1 }}
  ],
  "payment_method": "Credit Card",
  "tax_amount": 2.57,
  "currency": "USD"
}}
```

Return ONLY the JSON object, nothing else."""
            )

            # Extract JSON from the LLM response
            json_str = extract_json_from_text(receipt_data.output)

            if not json_str:
                raise ValueError("Could not extract valid JSON from the LLM response")

            # Parse the JSON data
            try:
                data = json.loads(json_str)

                # Convert string date to datetime
                if isinstance(data.get('date'), str):
                    data['date'] = datetime.fromisoformat(data['date'].replace('Z', '+00:00'))

                # Create ReceiptItem objects
                if 'items' in data:
                    items = []
                    for item_data in data['items']:
                        items.append(ReceiptItem(**item_data))
                    data['items'] = items

                # Create Receipt object
                receipt_obj = Receipt(**data)

                # Add the image path
                receipt_obj.image_path = image_path

            except (json.JSONDecodeError, ValueError) as e:
                raise ValueError(f"Failed to parse receipt data: {str(e)}")

            return ReceiptOCRResult(
                success=True,
                receipt=receipt_obj,
                confidence_score=0.9,  # This would be provided by a real OCR system
                error_message=None
            )

    except Exception as e:
        logfire.error(f"Receipt processing failed: {str(e)}")
        return ReceiptOCRResult(
            success=False,
            receipt=None,
            confidence_score=None,
            error_message=f"Failed to process receipt: {str(e)}"
        )


async def process_receipts_in_folder(folder_path: Optional[Union[str, Path]] = None) -> List[ReceiptOCRResult]:
    """
    Process all receipt images in a folder.

    Args:
        folder_path: Path to the folder containing receipt images

    Returns:
        List of ReceiptOCRResult objects
    """
    # Use the ROOT_DIR if folder_path is not provided
    if folder_path is None:
        folder_path = ROOT_DIR

    # Convert to Path object if it's a string
    folder_path_obj = Path(folder_path) if isinstance(folder_path, str) else folder_path

    # Get all image files in the folder
    image_files = []

    # Support for various image and document formats
    supported_extensions = [
        # Images
        '.jpg', '.jpeg', '.png', '.tiff', '.bmp', '.gif',
        # Documents
        '.pdf'
    ]

    for ext in supported_extensions:
        # Case-insensitive glob pattern
        for pattern in [f"*{ext}", f"*{ext.upper()}"]:
            image_files.extend(folder_path_obj.glob(pattern))

    # Sort files by modification time (newest first)
    image_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

    if not image_files:
        print(f"No receipt images found in {folder_path}")
        return []

    print(f"Found {len(image_files)} receipt images to process")

    results = []
    for image_file in image_files:
        print(f"Processing {image_file}...")
        result = await process_receipt_image(str(image_file))

        if result.success and result.receipt:
            # Save to database
            receipt_id = await save_receipt(result.receipt)
            print(f"✅ Saved receipt to database with ID {receipt_id}")
            print(f"   Store: {result.receipt.store_name}")
            print(f"   Date: {result.receipt.date}")
            print(f"   Total: {result.receipt.total_amount}")
            print(f"   Items: {len(result.receipt.items)}")
        else:
            print(f"❌ Failed to process receipt: {result.error_message}")

        results.append(result)

    return results


async def process_new_receipts(folder_path: Optional[Union[str, Path]] = None) -> List[ReceiptOCRResult]:
    """
    Process only new receipt images (added today).

    Args:
        folder_path: Path to the folder containing receipt images

    Returns:
        List of ReceiptOCRResult objects
    """
    # Use the ROOT_DIR if folder_path is not provided
    if folder_path is None:
        folder_path = ROOT_DIR

    # Convert to Path object if it's a string
    folder_path_obj = Path(folder_path) if isinstance(folder_path, str) else folder_path

    today = datetime.now().date()

    # Get all image files in the folder that were created today
    image_files = []

    # Support for various image and document formats
    supported_extensions = [
        # Images
        '.jpg', '.jpeg', '.png', '.tiff', '.bmp', '.gif',
        # Documents
        '.pdf'
    ]

    for ext in supported_extensions:
        # Case-insensitive glob pattern
        for pattern in [f"*{ext}", f"*{ext.upper()}"]:
            for file_path in folder_path_obj.glob(pattern):
                # Check if file was created today
                file_ctime = datetime.fromtimestamp(file_path.stat().st_ctime).date()
                if file_ctime == today:
                    image_files.append(file_path)

    # Sort files by modification time (newest first)
    image_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

    if not image_files:
        print(f"No new receipt images found in {folder_path_obj} today")
        return []

    print(f"Found {len(image_files)} new receipt images to process")

    results = []
    for image_file in image_files:
        print(f"Processing new receipt: {image_file}...")
        result = await process_receipt_image(str(image_file))

        if result.success and result.receipt:
            # Save to database
            receipt_id = await save_receipt(result.receipt)
            print(f"✅ Saved receipt to database with ID {receipt_id}")
            print(f"   Store: {result.receipt.store_name}")
            print(f"   Date: {result.receipt.date}")
            print(f"   Total: {result.receipt.total_amount}")
            print(f"   Items: {len(result.receipt.items)}")
        else:
            print(f"❌ Failed to process receipt: {result.error_message}")

        results.append(result)

    return results


async def analyze_spending_command(query: str) -> str:
    """
    Analyze spending based on a natural language query.

    Args:
        query: Natural language query about spending

    Returns:
        Analysis result as a string
    """
    try:
        # Extract time period, category, and store from the query
        period = None
        category = None
        store_name = None

        # Simple keyword matching for time periods
        if "today" in query.lower():
            period = "today"
        elif "yesterday" in query.lower():
            period = "yesterday"
        elif "this week" in query.lower():
            period = "this_week"
        elif "last week" in query.lower():
            period = "last_week"
        elif "this month" in query.lower():
            period = "this_month"
        elif "last month" in query.lower():
            period = "last_month"
        elif "this year" in query.lower():
            period = "this_year"
        elif "last year" in query.lower():
            period = "last_year"

        # Extract category if mentioned
        category_keywords = ["groceries", "food", "dining", "restaurant", "electronics", "clothing", "entertainment", "utilities", "transportation"]
        for keyword in category_keywords:
            if keyword in query.lower():
                category = keyword
                break

        # Extract store name if mentioned
        # Get all store names from the database
        all_receipts = await get_receipts()
        store_names = set(receipt.store_name for receipt in all_receipts)

        # Check if any store name is mentioned in the query
        for store in store_names:
            if store.lower() in query.lower():
                store_name = store
                break

        # Check for "at" or "from" followed by a store name
        at_from_match = re.search(r'(?:at|from)\s+([A-Za-z0-9\s]+)', query)
        if at_from_match and not store_name:
            potential_store = at_from_match.group(1).strip()
            # Find the closest match
            for store in store_names:
                if potential_store.lower() in store.lower() or store.lower() in potential_store.lower():
                    store_name = store
                    break

        # Get the analysis
        if store_name:
            print(f"Filtering by store: {store_name}")

        if period:
            analysis, period_description = await get_spending_for_period(period, category, store_name)
        else:
            # Default to all time if no period specified
            analysis = await analyze_spending(None, None, category, store_name)
            period_description = "all time"

        # If filtering by store, we need to manually filter the results
        if store_name:
            # Get all receipts for the store
            store_receipts = await get_receipts(store_name=store_name)

            # Calculate total spent at this store
            store_total = sum(receipt.total_amount for receipt in store_receipts)

            # Create a custom result
            result = f"Total spending at {store_name}: ${store_total:.2f}\n"
            result += f"Number of receipts: {len(store_receipts)}\n"

            # Return early with the store-specific result
            return result

        # Format the result
        result = f"Total spending for {period_description}: ${analysis.total_spent:.2f}\n"
        result += f"Number of receipts: {analysis.receipt_count}\n"

        if analysis.by_category:
            result += "\nSpending by category:\n"
            for cat, amount in analysis.by_category.items():
                result += f"  {cat}: ${amount:.2f}\n"

        if analysis.by_store:
            result += "\nSpending by store:\n"
            for store, amount in analysis.by_store.items():
                result += f"  {store}: ${amount:.2f}\n"

        return result

    except Exception as e:
        logfire.error(f"Analysis failed: {str(e)}")
        return f"Failed to analyze spending: {str(e)}"


async def main():
    """Main function to run the receipt processing agent."""
    try:
        print("🧾 Noa Receipt Processing Agent 🧾")
        print("----------------------------------")

        # Initialize the database
        print("Initializing database...")
        await init_db()
        print("Database initialized successfully")

        # Check command line arguments
        if len(sys.argv) < 2:
            print("\nUsage: python -m noa.app [command]")
            print("\nCommands:")
            print("  process-all  - Process all receipts in the folder")
            print("  process-new  - Process only new receipts (added today)")
            print("  analyze      - Analyze spending based on a query")
            print("\nExamples:")
            print("  python -m noa.app process-all")
            print("  python -m noa.app process-new")
            print("  python -m noa.app analyze \"how much did I spend on groceries last month\"")
            return

        command = sys.argv[1]

        if command == "process-all":
            print("\n📄 Processing all receipts in folder...")
            print(f"Looking in folder: {ROOT_DIR}")
            results = await process_receipts_in_folder()

            if results:
                success_count = sum(1 for r in results if r.success)
                fail_count = sum(1 for r in results if not r.success)

                print("\n📊 Summary:")
                print(f"  Total receipts processed: {len(results)}")
                print(f"  Successfully processed: {success_count}")
                print(f"  Failed to process: {fail_count}")

                if success_count > 0:
                    print("\n✅ Successfully processed receipts have been saved to the database")
            else:
                print("\n❌ No receipts found to process")

        elif command == "process-new":
            print("\n📄 Processing new receipts (added today)...")
            print(f"Looking in folder: {ROOT_DIR}")
            results = await process_new_receipts()

            if results:
                success_count = sum(1 for r in results if r.success)
                fail_count = sum(1 for r in results if not r.success)

                print("\n📊 Summary:")
                print(f"  Total new receipts processed: {len(results)}")
                print(f"  Successfully processed: {success_count}")
                print(f"  Failed to process: {fail_count}")

                if success_count > 0:
                    print("\n✅ Successfully processed receipts have been saved to the database")
            else:
                print("\n❌ No new receipts found to process")

        elif command == "analyze" and len(sys.argv) > 2:
            query = " ".join(sys.argv[2:])
            print(f"\n📊 Analyzing spending: \"{query}\"")
            print("This may take a moment...")

            result = await analyze_spending_command(query)

            print("\n📊 Analysis Result:")
            print(result)

        else:
            print("\n❌ Invalid command")
            print("Run 'python -m noa.app' without arguments to see usage instructions")

    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        logfire.error(f"Application error: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
