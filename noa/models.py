from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class ReceiptItem(BaseModel):
    """Model for an individual item on a receipt."""
    name: str = Field(..., description="Name of the item")
    price: float = Field(..., description="Price of the item")
    quantity: float = Field(1.0, description="Quantity of the item")
    category: Optional[str] = Field(None, description="Category of the item (e.g., groceries, electronics)")
    
    @property
    def total_price(self) -> float:
        """Calculate the total price for this item (price * quantity)."""
        return self.price * self.quantity


class Receipt(BaseModel):
    """Model for a receipt."""
    store_name: str = Field(..., description="Name of the store or merchant")
    date: datetime = Field(..., description="Date and time of the purchase")
    total_amount: float = Field(..., description="Total amount on the receipt")
    items: List[ReceiptItem] = Field(default_factory=list, description="List of items on the receipt")
    payment_method: Optional[str] = Field(None, description="Method of payment (e.g., cash, credit card)")
    receipt_id: Optional[str] = Field(None, description="Unique identifier for the receipt")
    tax_amount: Optional[float] = Field(None, description="Tax amount on the receipt")
    currency: str = Field("USD", description="Currency of the receipt")
    image_path: Optional[str] = Field(None, description="Path to the receipt image")


class ReceiptOCRResult(BaseModel):
    """Model for the result of OCR processing on a receipt."""
    success: bool = Field(..., description="Whether OCR was successful")
    receipt: Optional[Receipt] = Field(None, description="Extracted receipt data if successful")
    error_message: Optional[str] = Field(None, description="Error message if OCR failed")
    confidence_score: Optional[float] = Field(None, description="Confidence score of the OCR result (0-1)")


class SpendingAnalysis(BaseModel):
    """Model for spending analysis results."""
    total_spent: float = Field(..., description="Total amount spent")
    period_start: datetime = Field(..., description="Start date of the analysis period")
    period_end: datetime = Field(..., description="End date of the analysis period")
    by_category: Optional[dict] = Field(None, description="Spending breakdown by category")
    by_store: Optional[dict] = Field(None, description="Spending breakdown by store")
    by_date: Optional[dict] = Field(None, description="Spending breakdown by date")
    receipt_count: int = Field(..., description="Number of receipts in the analysis")
