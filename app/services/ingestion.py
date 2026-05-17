import pandas as pd
import io
import hashlib
from datetime import datetime
from typing import List, Dict, Tuple
from sqlalchemy.orm import Session
from app.models.transaction import Transaction


# Required columns for valid transaction data
REQUIRED_COLUMNS = {"date", "amount", "description"}
OPTIONAL_COLUMNS = {"transaction_type", "reference_id", "category"}


def generate_reference_id(row: pd.Series) -> str:
    """Generate a unique reference ID for deduplication based on transaction data."""
    raw = f"{row['date']}_{row['amount']}_{row['description']}"
    return hashlib.md5(raw.encode()).hexdigest()


def validate_dataframe(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    """
    Validate and clean the ingested dataframe.
    Returns cleaned dataframe and list of validation errors.
    """
    errors = []

    # Check required columns exist
    missing_cols = REQUIRED_COLUMNS - set(df.columns.str.lower())
    if missing_cols:
        errors.append(f"Missing required columns: {missing_cols}")
        return pd.DataFrame(), errors

    # Normalize column names to lowercase
    df.columns = df.columns.str.lower().str.strip()

    # Drop completely empty rows
    df = df.dropna(how="all")

    # Validate and parse dates
    try:
        df["date"] = pd.to_datetime(df["date"], utc=True)
    except Exception as e:
        errors.append(f"Date parsing error: {str(e)}")
        return pd.DataFrame(), errors

    # Validate amounts are numeric
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    invalid_amounts = df["amount"].isna().sum()
    if invalid_amounts > 0:
        errors.append(f"{invalid_amounts} rows have invalid (non-numeric) amounts")
        df = df.dropna(subset=["amount"])

    # Validate descriptions are non-empty
    df["description"] = df["description"].astype(str).str.strip()
    empty_descriptions = (df["description"] == "").sum()
    if empty_descriptions > 0:
        errors.append(f"{empty_descriptions} rows have empty descriptions")
        df = df[df["description"] != ""]

    # Set transaction_type if not provided
    if "transaction_type" not in df.columns:
        df["transaction_type"] = df["amount"].apply(
            lambda x: "credit" if x > 0 else "debit"
        )
    else:
        df["transaction_type"] = df["transaction_type"].str.lower().str.strip()
        # Default invalid types based on amount sign
        valid_types = df["transaction_type"].isin(["credit", "debit"])
        df.loc[~valid_types, "transaction_type"] = df.loc[~valid_types, "amount"].apply(
            lambda x: "credit" if x > 0 else "debit"
        )

    # Generate reference IDs for deduplication
    if "reference_id" not in df.columns or df["reference_id"].isna().all():
        df["reference_id"] = df.apply(generate_reference_id, axis=1)
    else:
        # Fill missing reference IDs
        mask = df["reference_id"].isna()
        df.loc[mask, "reference_id"] = df[mask].apply(generate_reference_id, axis=1)

    # Ensure amount is always positive (type indicates direction)
    df["amount"] = df["amount"].abs()

    return df, errors


def parse_csv(file_content: bytes) -> pd.DataFrame:
    """Parse CSV file content into a DataFrame."""
    return pd.read_csv(io.BytesIO(file_content))


def parse_json(file_content: bytes) -> pd.DataFrame:
    """Parse JSON file content into a DataFrame."""
    return pd.read_json(io.BytesIO(file_content))


def check_duplicates(db: Session, user_id: int, reference_ids: List[str]) -> set:
    """Check which reference IDs already exist in the database."""
    existing = (
        db.query(Transaction.reference_id)
        .filter(
            Transaction.user_id == user_id,
            Transaction.reference_id.in_(reference_ids),
        )
        .all()
    )
    return {row[0] for row in existing}


def ingest_transactions(
    db: Session,
    user_id: int,
    file_content: bytes,
    filename: str,
    file_type: str,
) -> Dict:
    """
    Main ingestion pipeline: parse, validate, deduplicate, and store transactions.

    Returns a summary dict with counts and errors.
    """
    # Parse file based on type
    if file_type == "csv":
        df = parse_csv(file_content)
    elif file_type == "json":
        df = parse_json(file_content)
    else:
        return {"error": f"Unsupported file type: {file_type}"}

    total_records = len(df)

    # Validate and clean
    df, validation_errors = validate_dataframe(df)

    if df.empty and validation_errors:
        return {
            "error": "Validation failed",
            "details": validation_errors,
            "total_records": total_records,
            "successful": 0,
        }

    # Check for duplicates
    reference_ids = df["reference_id"].tolist()
    existing_refs = check_duplicates(db, user_id, reference_ids)
    duplicates_count = len(df[df["reference_id"].isin(existing_refs)])

    # Filter out duplicates
    df = df[~df["reference_id"].isin(existing_refs)]

    # Create Transaction objects
    transactions = []
    for _, row in df.iterrows():
        txn = Transaction(
            user_id=user_id,
            date=row["date"],
            amount=row["amount"],
            description=row["description"],
            transaction_type=row["transaction_type"],
            reference_id=row["reference_id"],
            category=row.get("category") if pd.notna(row.get("category")) else None,
            source_file=filename,
        )
        transactions.append(txn)

    # Bulk insert
    db.bulk_save_objects(transactions)
    db.commit()

    return {
        "total_records": total_records,
        "successful": len(transactions),
        "failed": total_records - len(df) - duplicates_count,
        "duplicates_skipped": duplicates_count,
        "validation_errors": validation_errors,
    }
