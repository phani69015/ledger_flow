from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Optional, List


class TransactionCreate(BaseModel):
    """Schema for creating a single transaction."""
    date: datetime
    amount: float
    description: str
    transaction_type: str = Field(..., pattern="^(credit|debit)$")
    reference_id: Optional[str] = None
    category: Optional[str] = None


class TransactionUpdate(BaseModel):
    """Schema for updating a transaction."""
    category: Optional[str] = None
    description: Optional[str] = None
    transaction_type: Optional[str] = None


class TransactionResponse(BaseModel):
    """Schema for transaction response."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    date: datetime
    amount: float
    description: str
    transaction_type: str
    reference_id: Optional[str] = None
    category: Optional[str] = None
    category_confidence: Optional[float] = None
    is_anomaly: bool = False
    anomaly_score: Optional[float] = None
    anomaly_reason: Optional[str] = None
    source_file: Optional[str] = None
    account_no: Optional[str] = None
    created_at: Optional[datetime] = None


class UploadResponse(BaseModel):
    """Response after file upload and processing."""
    filename: str
    total_records: int
    successful: int
    failed: int
    duplicates_skipped: int
    anomalies_detected: int
    categories_assigned: int
    message: str


class CategoryBreakdown(BaseModel):
    """Category spending breakdown."""
    category: str
    total_amount: float
    transaction_count: int
    percentage: float
    avg_amount: float


class AnomalyReport(BaseModel):
    """Anomaly detection report."""
    transaction_id: int
    date: datetime
    amount: float
    description: str
    anomaly_score: float
    anomaly_reason: str


class AnalyticsSummary(BaseModel):
    """Overall analytics summary."""
    total_transactions: int
    total_income: float
    total_expenses: float
    net_balance: float
    avg_transaction_amount: float
    total_anomalies: int
    top_categories: List[CategoryBreakdown]
    date_range_start: Optional[datetime] = None
    date_range_end: Optional[datetime] = None


class MonthlyTrend(BaseModel):
    """Monthly spending trend."""
    month: str
    income: float
    expenses: float
    net: float
    transaction_count: int
