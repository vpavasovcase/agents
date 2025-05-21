import os
from datetime import datetime
from typing import List, Optional, Dict, Any

import asyncpg
from pydantic import BaseModel

from noa.models import Receipt, ReceiptItem


async def get_connection():
    """Get a connection to the PostgreSQL database."""
    return await asyncpg.connect(
        host=os.getenv("DATABASE_HOST", "postgres"),
        port=int(os.getenv("DATABASE_PORT", "5432")),
        user=os.getenv("DATABASE_USER", "postgres"),
        password=os.getenv("DATABASE_PASSWORD", "postgres"),
        database=os.getenv("DATABASE_NAME", "postgres"),
    )


async def init_db():
    """Initialize the database schema."""
    conn = await get_connection()
    try:
        # Create receipts table
        await conn.execute('''
        CREATE TABLE IF NOT EXISTS receipts (
            id SERIAL PRIMARY KEY,
            store_name TEXT NOT NULL,
            date TIMESTAMP NOT NULL,
            total_amount FLOAT NOT NULL,
            payment_method TEXT,
            receipt_id TEXT,
            tax_amount FLOAT,
            currency TEXT NOT NULL DEFAULT 'USD',
            image_path TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
        ''')

        # Create receipt_items table
        await conn.execute('''
        CREATE TABLE IF NOT EXISTS receipt_items (
            id SERIAL PRIMARY KEY,
            receipt_id INTEGER REFERENCES receipts(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            price FLOAT NOT NULL,
            quantity FLOAT NOT NULL DEFAULT 1.0,
            category TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
        ''')
    finally:
        await conn.close()


async def save_receipt(receipt: Receipt) -> int:
    """Save a receipt to the database and return its ID."""
    conn = await get_connection()
    try:
        # Insert receipt
        receipt_id = await conn.fetchval('''
        INSERT INTO receipts (store_name, date, total_amount, payment_method, receipt_id, tax_amount, currency, image_path)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        RETURNING id
        ''', receipt.store_name, receipt.date, receipt.total_amount, receipt.payment_method,
        receipt.receipt_id, receipt.tax_amount, receipt.currency, receipt.image_path)

        # Insert receipt items
        for item in receipt.items:
            await conn.execute('''
            INSERT INTO receipt_items (receipt_id, name, price, quantity, category)
            VALUES ($1, $2, $3, $4, $5)
            ''', receipt_id, item.name, item.price, item.quantity, item.category)

        return receipt_id
    finally:
        await conn.close()


async def get_receipt(receipt_id: int) -> Optional[Receipt]:
    """Get a receipt by ID."""
    conn = await get_connection()
    try:
        # Get receipt
        receipt_row = await conn.fetchrow('''
        SELECT * FROM receipts WHERE id = $1
        ''', receipt_id)

        if not receipt_row:
            return None

        # Get receipt items
        item_rows = await conn.fetch('''
        SELECT * FROM receipt_items WHERE receipt_id = $1
        ''', receipt_id)

        # Convert to Receipt model
        items = [
            ReceiptItem(
                name=row['name'],
                price=row['price'],
                quantity=row['quantity'],
                category=row['category']
            )
            for row in item_rows
        ]

        return Receipt(
            store_name=receipt_row['store_name'],
            date=receipt_row['date'],
            total_amount=receipt_row['total_amount'],
            items=items,
            payment_method=receipt_row['payment_method'],
            receipt_id=receipt_row['receipt_id'],
            tax_amount=receipt_row['tax_amount'],
            currency=receipt_row['currency'],
            image_path=receipt_row['image_path']
        )
    finally:
        await conn.close()


async def get_receipts(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    store_name: Optional[str] = None,
    category: Optional[str] = None
) -> List[Receipt]:
    """Get receipts with optional filters."""
    conn = await get_connection()
    try:
        # Build query
        query = "SELECT id FROM receipts WHERE 1=1"
        params = []
        param_idx = 1

        if start_date:
            query += f" AND date >= ${param_idx}"
            params.append(start_date)
            param_idx += 1

        if end_date:
            query += f" AND date <= ${param_idx}"
            params.append(end_date)
            param_idx += 1

        if store_name:
            query += f" AND store_name ILIKE ${param_idx}"
            params.append(f"%{store_name}%")
            param_idx += 1

        # Execute query
        receipt_ids = await conn.fetch(query, *params)

        # If category filter is provided, we need to filter after fetching the receipts
        receipts = []
        for row in receipt_ids:
            receipt = await get_receipt(row['id'])
            if receipt:
                # Filter by category if specified
                if category and not any(item.category == category for item in receipt.items if item.category):
                    continue
                receipts.append(receipt)

        return receipts
    finally:
        await conn.close()


async def get_spending_by_category(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> Dict[str, float]:
    """Get spending breakdown by category."""
    conn = await get_connection()
    try:
        query = """
        SELECT ri.category, SUM(ri.price * ri.quantity) as total
        FROM receipt_items ri
        JOIN receipts r ON ri.receipt_id = r.id
        WHERE ri.category IS NOT NULL
        """
        params = []
        param_idx = 1

        if start_date:
            query += f" AND r.date >= ${param_idx}"
            params.append(start_date)
            param_idx += 1

        if end_date:
            query += f" AND r.date <= ${param_idx}"
            params.append(end_date)
            param_idx += 1

        query += " GROUP BY ri.category"

        rows = await conn.fetch(query, *params)
        return {row['category']: row['total'] for row in rows}
    finally:
        await conn.close()


async def get_spending_by_store(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> Dict[str, float]:
    """Get spending breakdown by store."""
    conn = await get_connection()
    try:
        query = """
        SELECT store_name, SUM(total_amount) as total
        FROM receipts
        WHERE 1=1
        """
        params = []
        param_idx = 1

        if start_date:
            query += f" AND date >= ${param_idx}"
            params.append(start_date)
            param_idx += 1

        if end_date:
            query += f" AND date <= ${param_idx}"
            params.append(end_date)
            param_idx += 1

        query += " GROUP BY store_name"

        rows = await conn.fetch(query, *params)
        return {row['store_name']: row['total'] for row in rows}
    finally:
        await conn.close()
