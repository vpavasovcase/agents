from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from noa.db import get_receipts, get_spending_by_category, get_spending_by_store
from noa.models import Receipt, SpendingAnalysis


async def analyze_spending(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    store_name: Optional[str] = None,
    category: Optional[str] = None
) -> SpendingAnalysis:
    """
    Analyze spending based on receipts in the database.
    
    Args:
        start_date: Optional start date for the analysis period
        end_date: Optional end date for the analysis period
        store_name: Optional store name to filter by
        category: Optional category to filter by
        
    Returns:
        SpendingAnalysis object with the results
    """
    # Get receipts based on filters
    receipts = await get_receipts(
        start_date=start_date,
        end_date=end_date,
        store_name=store_name,
        category=category
    )
    
    # Calculate total spent
    total_spent = sum(receipt.total_amount for receipt in receipts)
    
    # Determine actual date range from the data
    if receipts:
        actual_start = min(receipt.date for receipt in receipts)
        actual_end = max(receipt.date for receipt in receipts)
    else:
        actual_start = start_date or datetime.now() - timedelta(days=30)
        actual_end = end_date or datetime.now()
    
    # Get spending breakdowns
    by_category = None
    by_store = None
    
    if not category:  # Only get category breakdown if not filtering by category
        by_category = await get_spending_by_category(start_date, end_date)
    
    if not store_name:  # Only get store breakdown if not filtering by store
        by_store = await get_spending_by_store(start_date, end_date)
    
    # Create spending by date breakdown
    by_date = {}
    for receipt in receipts:
        date_str = receipt.date.strftime('%Y-%m-%d')
        by_date[date_str] = by_date.get(date_str, 0) + receipt.total_amount
    
    return SpendingAnalysis(
        total_spent=total_spent,
        period_start=actual_start,
        period_end=actual_end,
        by_category=by_category,
        by_store=by_store,
        by_date=by_date,
        receipt_count=len(receipts)
    )


async def get_spending_for_period(
    period: str,
    category: Optional[str] = None,
    store_name: Optional[str] = None
) -> Tuple[SpendingAnalysis, str]:
    """
    Get spending analysis for a specific time period.
    
    Args:
        period: String indicating the period ('today', 'yesterday', 'this_week', 'last_week', 
               'this_month', 'last_month', 'this_year', 'last_year')
        category: Optional category to filter by
        store_name: Optional store name to filter by
        
    Returns:
        Tuple of (SpendingAnalysis, period_description)
    """
    now = datetime.now()
    start_date = None
    end_date = None
    period_description = ""
    
    if period == 'today':
        start_date = datetime(now.year, now.month, now.day)
        end_date = now
        period_description = f"today ({start_date.strftime('%Y-%m-%d')})"
    
    elif period == 'yesterday':
        yesterday = now - timedelta(days=1)
        start_date = datetime(yesterday.year, yesterday.month, yesterday.day)
        end_date = datetime(yesterday.year, yesterday.month, yesterday.day, 23, 59, 59)
        period_description = f"yesterday ({start_date.strftime('%Y-%m-%d')})"
    
    elif period == 'this_week':
        # Assuming week starts on Monday (0 = Monday in Python's datetime)
        days_since_monday = now.weekday()
        start_date = datetime(now.year, now.month, now.day) - timedelta(days=days_since_monday)
        end_date = now
        period_description = f"this week ({start_date.strftime('%Y-%m-%d')} to {now.strftime('%Y-%m-%d')})"
    
    elif period == 'last_week':
        # Last week's Monday to Sunday
        days_since_monday = now.weekday()
        start_of_this_week = datetime(now.year, now.month, now.day) - timedelta(days=days_since_monday)
        end_of_last_week = start_of_this_week - timedelta(seconds=1)
        start_of_last_week = end_of_last_week - timedelta(days=6)
        start_date = start_of_last_week
        end_date = end_of_last_week
        period_description = f"last week ({start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')})"
    
    elif period == 'this_month':
        start_date = datetime(now.year, now.month, 1)
        end_date = now
        period_description = f"this month ({start_date.strftime('%Y-%m-%d')} to {now.strftime('%Y-%m-%d')})"
    
    elif period == 'last_month':
        if now.month == 1:
            start_date = datetime(now.year - 1, 12, 1)
            end_date = datetime(now.year, now.month, 1) - timedelta(seconds=1)
        else:
            start_date = datetime(now.year, now.month - 1, 1)
            end_date = datetime(now.year, now.month, 1) - timedelta(seconds=1)
        period_description = f"last month ({start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')})"
    
    elif period == 'this_year':
        start_date = datetime(now.year, 1, 1)
        end_date = now
        period_description = f"this year ({start_date.strftime('%Y-%m-%d')} to {now.strftime('%Y-%m-%d')})"
    
    elif period == 'last_year':
        start_date = datetime(now.year - 1, 1, 1)
        end_date = datetime(now.year, 1, 1) - timedelta(seconds=1)
        period_description = f"last year ({start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')})"
    
    else:
        # Default to last 30 days
        start_date = now - timedelta(days=30)
        end_date = now
        period_description = f"the last 30 days ({start_date.strftime('%Y-%m-%d')} to {now.strftime('%Y-%m-%d')})"
    
    analysis = await analyze_spending(
        start_date=start_date,
        end_date=end_date,
        category=category,
        store_name=store_name
    )
    
    return analysis, period_description
