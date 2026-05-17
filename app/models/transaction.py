from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Transaction(Base):
    """Financial transaction model with categorization and anomaly flags."""

    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Transaction details
    date = Column(DateTime(timezone=True), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    description = Column(Text, nullable=False)
    transaction_type = Column(String(20), nullable=False)  # credit / debit
    reference_id = Column(String(100), unique=True, nullable=True)  # for deduplication

    # AI-categorized fields
    category = Column(String(100), nullable=True)
    category_confidence = Column(Float, nullable=True)  # 0.0 - 1.0

    # Anomaly detection
    is_anomaly = Column(Boolean, default=False)
    anomaly_score = Column(Float, nullable=True)
    anomaly_reason = Column(String(255), nullable=True)

    # Metadata
    source_file = Column(String(255), nullable=True)  # which file it was ingested from
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    owner = relationship("User", back_populates="transactions")

    def __repr__(self):
        return f"<Transaction(id={self.id}, amount={self.amount}, category={self.category})>"
