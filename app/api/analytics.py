from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from typing import Optional
from datetime import datetime, timedelta, timezone
from app.database import get_db
from app.models.user import User
from app.models.transaction import Transaction
from app.schemas.transaction import (
    AnalyticsSummary,
    CategoryBreakdown,
    AnomalyReport,
    MonthlyTrend,
)
from app.api.deps import get_current_user

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/summary", response_model=AnalyticsSummary)
def get_analytics_summary(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get comprehensive analytics summary including:
    - Total income and expenses
    - Net balance
    - Average transaction amount
    - Anomaly count
    - Top spending categories
    """
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

    # Base query for user's transactions within the date range
    base_query = db.query(Transaction).filter(
        Transaction.user_id == current_user.id,
        Transaction.date >= cutoff_date,
    )

    # Total counts
    total_transactions = base_query.count()

    if total_transactions == 0:
        return AnalyticsSummary(
            total_transactions=0,
            total_income=0.0,
            total_expenses=0.0,
            net_balance=0.0,
            avg_transaction_amount=0.0,
            total_anomalies=0,
            top_categories=[],
        )

    # Income (credits)
    total_income = (
        db.query(func.coalesce(func.sum(Transaction.amount), 0))
        .filter(
            Transaction.user_id == current_user.id,
            Transaction.date >= cutoff_date,
            Transaction.transaction_type == "credit",
        )
        .scalar()
    ) or 0.0

    # Expenses (debits)
    total_expenses = (
        db.query(func.coalesce(func.sum(Transaction.amount), 0))
        .filter(
            Transaction.user_id == current_user.id,
            Transaction.date >= cutoff_date,
            Transaction.transaction_type == "debit",
        )
        .scalar()
    ) or 0.0

    # Average amount
    avg_amount = (
        db.query(func.avg(Transaction.amount))
        .filter(
            Transaction.user_id == current_user.id,
            Transaction.date >= cutoff_date,
        )
        .scalar()
    ) or 0.0

    # Anomaly count
    total_anomalies = (
        base_query.filter(Transaction.is_anomaly == True).count()
    )

    # Top categories (expenses only)
    category_data = (
        db.query(
            Transaction.category,
            func.sum(Transaction.amount).label("total"),
            func.count(Transaction.id).label("count"),
            func.avg(Transaction.amount).label("avg"),
        )
        .filter(
            Transaction.user_id == current_user.id,
            Transaction.date >= cutoff_date,
            Transaction.transaction_type == "debit",
            Transaction.category.isnot(None),
        )
        .group_by(Transaction.category)
        .order_by(func.sum(Transaction.amount).desc())
        .limit(10)
        .all()
    )

    top_categories = []
    for cat in category_data:
        percentage = (cat.total / total_expenses * 100) if total_expenses > 0 else 0
        top_categories.append(
            CategoryBreakdown(
                category=cat.category or "Uncategorized",
                total_amount=round(cat.total, 2),
                transaction_count=cat.count,
                percentage=round(percentage, 1),
                avg_amount=round(cat.avg, 2),
            )
        )

    # Date range
    date_range = (
        db.query(
            func.min(Transaction.date),
            func.max(Transaction.date),
        )
        .filter(
            Transaction.user_id == current_user.id,
            Transaction.date >= cutoff_date,
        )
        .first()
    )

    return AnalyticsSummary(
        total_transactions=total_transactions,
        total_income=round(total_income, 2),
        total_expenses=round(total_expenses, 2),
        net_balance=round(total_income - total_expenses, 2),
        avg_transaction_amount=round(avg_amount, 2),
        total_anomalies=total_anomalies,
        top_categories=top_categories,
        date_range_start=date_range[0] if date_range else None,
        date_range_end=date_range[1] if date_range else None,
    )


@router.get("/categories")
def get_category_breakdown(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get detailed spending breakdown by category."""
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

    categories = (
        db.query(
            Transaction.category,
            func.sum(Transaction.amount).label("total"),
            func.count(Transaction.id).label("count"),
            func.avg(Transaction.amount).label("avg"),
            func.min(Transaction.amount).label("min_amount"),
            func.max(Transaction.amount).label("max_amount"),
        )
        .filter(
            Transaction.user_id == current_user.id,
            Transaction.date >= cutoff_date,
        )
        .group_by(Transaction.category)
        .order_by(func.sum(Transaction.amount).desc())
        .all()
    )

    total_amount = sum(cat.total for cat in categories) if categories else 0

    return [
        {
            "category": cat.category or "Uncategorized",
            "total_amount": round(cat.total, 2),
            "transaction_count": cat.count,
            "percentage": round((cat.total / total_amount * 100) if total_amount > 0 else 0, 1),
            "avg_amount": round(cat.avg, 2),
            "min_amount": round(cat.min_amount, 2),
            "max_amount": round(cat.max_amount, 2),
        }
        for cat in categories
    ]


@router.get("/anomalies")
def get_anomaly_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all detected anomalies with details."""
    anomalies = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == current_user.id,
            Transaction.is_anomaly == True,
        )
        .order_by(Transaction.anomaly_score.desc())
        .all()
    )

    return {
        "total_anomalies": len(anomalies),
        "anomalies": [
            {
                "transaction_id": txn.id,
                "date": txn.date.isoformat() if txn.date else None,
                "amount": txn.amount,
                "description": txn.description,
                "category": txn.category,
                "anomaly_score": txn.anomaly_score,
                "anomaly_reason": txn.anomaly_reason,
            }
            for txn in anomalies
        ],
    }


@router.get("/trends")
def get_monthly_trends(
    months: int = Query(6, ge=1, le=24),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get monthly income/expense trends."""
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=months * 30)

    transactions = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == current_user.id,
            Transaction.date >= cutoff_date,
        )
        .order_by(Transaction.date.asc())
        .all()
    )

    # Group by month
    monthly_data = {}
    for txn in transactions:
        month_key = txn.date.strftime("%Y-%m")
        if month_key not in monthly_data:
            monthly_data[month_key] = {"income": 0.0, "expenses": 0.0, "count": 0}

        if txn.transaction_type == "credit":
            monthly_data[month_key]["income"] += txn.amount
        else:
            monthly_data[month_key]["expenses"] += txn.amount
        monthly_data[month_key]["count"] += 1

    trends = []
    for month, data in sorted(monthly_data.items()):
        trends.append(
            MonthlyTrend(
                month=month,
                income=round(data["income"], 2),
                expenses=round(data["expenses"], 2),
                net=round(data["income"] - data["expenses"], 2),
                transaction_count=data["count"],
            )
        )

    return trends
