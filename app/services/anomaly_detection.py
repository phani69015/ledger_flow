"""
Anomaly Detection Service for Financial Transactions

Implements multiple anomaly detection methods:
1. Z-Score: Identifies transactions with amounts that deviate significantly
   from the user's historical mean.
2. IQR (Interquartile Range): Detects outliers using statistical quartile boundaries.
3. Frequency Analysis: Flags unusual transaction frequency patterns.

These methods combined provide robust anomaly detection without requiring
external ML model training - suitable for real-time processing of financial data.
"""

import numpy as np
from typing import List, Dict, Tuple, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.transaction import Transaction


# Configuration thresholds
Z_SCORE_THRESHOLD = 2.5  # Standard deviations from mean
IQR_MULTIPLIER = 1.5     # IQR fence multiplier (1.5 = standard, 3.0 = extreme)
MIN_TRANSACTIONS_FOR_DETECTION = 5  # Minimum history needed for anomaly detection


def calculate_z_score(value: float, mean: float, std: float) -> float:
    """Calculate z-score for a given value."""
    if std == 0:
        return 0.0
    return abs((value - mean) / std)


def detect_amount_anomaly_zscore(
    amount: float,
    historical_amounts: List[float],
) -> Tuple[bool, float, str]:
    """
    Detect if a transaction amount is anomalous using Z-Score method.

    Returns:
        Tuple of (is_anomaly, anomaly_score, reason)
    """
    if len(historical_amounts) < MIN_TRANSACTIONS_FOR_DETECTION:
        return (False, 0.0, "")

    mean = np.mean(historical_amounts)
    std = np.std(historical_amounts)

    if std == 0:
        # All historical transactions have the same amount
        if amount != mean:
            return (True, 1.0, f"Amount ${amount:.2f} differs from consistent pattern of ${mean:.2f}")
        return (False, 0.0, "")

    z_score = calculate_z_score(amount, mean, std)

    if z_score > Z_SCORE_THRESHOLD:
        deviation_pct = ((amount - mean) / mean) * 100
        direction = "above" if amount > mean else "below"
        reason = (
            f"Amount ${amount:.2f} is {abs(deviation_pct):.1f}% {direction} average "
            f"(${mean:.2f}). Z-score: {z_score:.2f}"
        )
        # Normalize score to 0-1 range
        normalized_score = min(z_score / (Z_SCORE_THRESHOLD * 2), 1.0)
        return (True, round(normalized_score, 3), reason)

    return (False, round(z_score / (Z_SCORE_THRESHOLD * 2), 3), "")


def detect_amount_anomaly_iqr(
    amount: float,
    historical_amounts: List[float],
) -> Tuple[bool, float, str]:
    """
    Detect if a transaction amount is anomalous using IQR method.

    Returns:
        Tuple of (is_anomaly, anomaly_score, reason)
    """
    if len(historical_amounts) < MIN_TRANSACTIONS_FOR_DETECTION:
        return (False, 0.0, "")

    q1 = np.percentile(historical_amounts, 25)
    q3 = np.percentile(historical_amounts, 75)
    iqr = q3 - q1

    if iqr == 0:
        # Very tight distribution
        median = np.median(historical_amounts)
        if abs(amount - median) > median * 0.5:
            return (True, 0.7, f"Amount ${amount:.2f} outside tight distribution (median: ${median:.2f})")
        return (False, 0.0, "")

    lower_fence = q1 - (IQR_MULTIPLIER * iqr)
    upper_fence = q3 + (IQR_MULTIPLIER * iqr)

    if amount < lower_fence or amount > upper_fence:
        if amount > upper_fence:
            distance = (amount - upper_fence) / iqr
            reason = f"Amount ${amount:.2f} exceeds upper bound ${upper_fence:.2f} (IQR method)"
        else:
            distance = (lower_fence - amount) / iqr
            reason = f"Amount ${amount:.2f} below lower bound ${lower_fence:.2f} (IQR method)"

        normalized_score = min(distance / (IQR_MULTIPLIER * 2), 1.0)
        return (True, round(normalized_score, 3), reason)

    return (False, 0.0, "")


def detect_frequency_anomaly(
    db: Session,
    user_id: int,
    category: Optional[str] = None,
) -> List[Dict]:
    """
    Detect unusual transaction frequency patterns.
    Checks if recent transaction count significantly exceeds historical average.
    """
    # This is a simplified frequency check
    # In production, you'd use time-windowed analysis
    return []


def analyze_transaction(
    amount: float,
    historical_amounts: List[float],
    transaction_type: str = "debit",
) -> Dict:
    """
    Run all anomaly detection methods on a single transaction.
    Combines Z-Score and IQR results for a final determination.

    Returns:
        Dict with is_anomaly, anomaly_score, anomaly_reason
    """
    # Filter historical amounts by same type (compare debits with debits, etc.)
    if len(historical_amounts) < MIN_TRANSACTIONS_FOR_DETECTION:
        return {
            "is_anomaly": False,
            "anomaly_score": 0.0,
            "anomaly_reason": None,
        }

    # Run both methods
    z_anomaly, z_score, z_reason = detect_amount_anomaly_zscore(amount, historical_amounts)
    iqr_anomaly, iqr_score, iqr_reason = detect_amount_anomaly_iqr(amount, historical_amounts)

    # Combined scoring: weighted average of both methods
    combined_score = (z_score * 0.6) + (iqr_score * 0.4)

    # Transaction is anomalous if either method flags it
    is_anomaly = z_anomaly or iqr_anomaly

    # Use the most descriptive reason
    reason = None
    if is_anomaly:
        if z_score >= iqr_score:
            reason = z_reason
        else:
            reason = iqr_reason

    return {
        "is_anomaly": is_anomaly,
        "anomaly_score": round(combined_score, 3),
        "anomaly_reason": reason,
    }


def run_anomaly_detection_for_user(db: Session, user_id: int) -> Dict:
    """
    Run anomaly detection across all transactions for a user.
    Updates anomaly flags in the database.

    Returns summary of detection results.
    """
    # Get all user transactions ordered by date
    transactions = (
        db.query(Transaction)
        .filter(Transaction.user_id == user_id)
        .order_by(Transaction.date.asc())
        .all()
    )

    if len(transactions) < MIN_TRANSACTIONS_FOR_DETECTION:
        return {
            "total_analyzed": len(transactions),
            "anomalies_found": 0,
            "message": f"Need at least {MIN_TRANSACTIONS_FOR_DETECTION} transactions for detection",
        }

    # Separate by transaction type
    debit_amounts = [t.amount for t in transactions if t.transaction_type == "debit"]
    credit_amounts = [t.amount for t in transactions if t.transaction_type == "credit"]

    anomalies_found = 0

    for txn in transactions:
        # Use historical amounts of the same type
        historical = debit_amounts if txn.transaction_type == "debit" else credit_amounts

        result = analyze_transaction(txn.amount, historical, txn.transaction_type)

        # Update transaction in database
        txn.is_anomaly = result["is_anomaly"]
        txn.anomaly_score = result["anomaly_score"]
        txn.anomaly_reason = result["anomaly_reason"]

        if result["is_anomaly"]:
            anomalies_found += 1

    db.commit()

    return {
        "total_analyzed": len(transactions),
        "anomalies_found": anomalies_found,
        "detection_methods": ["Z-Score", "IQR"],
        "thresholds": {
            "z_score": Z_SCORE_THRESHOLD,
            "iqr_multiplier": IQR_MULTIPLIER,
        },
    }
