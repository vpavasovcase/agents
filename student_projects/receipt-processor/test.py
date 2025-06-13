import asyncio
import os
from datetime import datetime

from noa.db import init_db, save_receipt, get_receipt, get_receipts
from noa.models import Receipt, ReceiptItem
from noa.analysis import analyze_spending, get_spending_for_period


async def test_database():
    """Test database operations."""
    print("Testing database operations...")
    
    # Initialize the database
    await init_db()
    
    # Create a test receipt
    receipt = Receipt(
        store_name="Test Store",
        date=datetime.now(),
        total_amount=100.0,
        items=[
            ReceiptItem(name="Item 1", price=50.0, quantity=1, category="Groceries"),
            ReceiptItem(name="Item 2", price=25.0, quantity=2, category="Electronics")
        ],
        payment_method="Credit Card",
        tax_amount=10.0,
        currency="USD",
        image_path="test.jpg"
    )
    
    # Save the receipt
    receipt_id = await save_receipt(receipt)
    print(f"Saved receipt with ID: {receipt_id}")
    
    # Get the receipt
    retrieved_receipt = await get_receipt(receipt_id)
    print(f"Retrieved receipt: {retrieved_receipt}")
    
    # Get all receipts
    all_receipts = await get_receipts()
    print(f"Retrieved {len(all_receipts)} receipts")
    
    return receipt_id


async def test_analysis(receipt_id):
    """Test spending analysis."""
    print("\nTesting spending analysis...")
    
    # Analyze all spending
    analysis = await analyze_spending()
    print(f"Total spending: ${analysis.total_spent:.2f}")
    print(f"By category: {analysis.by_category}")
    print(f"By store: {analysis.by_store}")
    
    # Test period analysis
    for period in ["today", "this_week", "this_month"]:
        analysis, description = await get_spending_for_period(period)
        print(f"Spending for {description}: ${analysis.total_spent:.2f}")


async def main():
    """Run all tests."""
    try:
        receipt_id = await test_database()
        await test_analysis(receipt_id)
        print("\nAll tests passed!")
    except Exception as e:
        print(f"Test failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
