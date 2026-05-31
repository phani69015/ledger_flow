"""
Transaction Ingestion Pipeline

Supports multiple file formats (CSV, JSON, XLSX) and auto-detects
bank statement formats using smart column mapping.

Pipeline stages:
1. Parse file (CSV/JSON/XLSX)
2. Detect format & normalize columns (smart column mapping)
3. Validate & clean data
4. Deduplicate against existing records
5. Bulk insert into database
"""

import pandas as pd
import io
import hashlib
from typing import List, Dict, Tuple, Optional
from sqlalchemy.orm import Session
from app.models.transaction import Transaction


# Required columns after normalization
REQUIRED_COLUMNS = {"date", "amount", "description"}

# Keywords for detecting column roles (fuzzy matching)
DATE_KEYWORDS = ["date", "txn date", "trans date", "transaction date"]
DATE_EXCLUDE = ["value", "posting"]
DESCRIPTION_KEYWORDS = ["transaction", "detail", "description", "narration", "particular", "remark"]
DEBIT_KEYWORDS = ["withdrawal", "debit", "dr", "paid out", "withdrawal amt"]
CREDIT_KEYWORDS = ["deposit", "credit", "cr", "paid in", "deposit amt"]
ACCOUNT_KEYWORDS = ["account", "acc", "acct"]
AMOUNT_KEYWORDS = ["amount", "amt"]


# ─── Column Detection ────────────────────────────────────────────────────────

def find_column(df: pd.DataFrame, keywords: List[str], exclude: List[str] = None, required: bool = True) -> Optional[str]:
    """
    Find a column whose name contains any of the keywords (case-insensitive).
    Excludes columns matching any exclude keywords.
    """
    for col in df.columns:
        col_lower = col.lower().strip()
        # Check exclusions first
        if exclude and any(ex in col_lower for ex in exclude):
            continue
        # Check if any keyword matches
        if any(kw in col_lower for kw in keywords):
            return col
    if required:
        return None
    return None


def detect_format(df: pd.DataFrame) -> str:
    """
    Detect the format of the uploaded file.

    Returns:
        'standard' - has date, amount, description columns
        'bank_statement' - has separate withdrawal/deposit columns
        'unknown' - cannot determine format
    """
    columns_lower = [c.lower().strip() for c in df.columns]

    # Check for standard format (date + amount + description)
    has_date = any("date" in c for c in columns_lower)
    has_amount = any("amount" in c and "withdrawal" not in c and "deposit" not in c
                     for c in columns_lower)
    has_desc = any(any(kw in c for kw in ["description", "detail", "narration"])
                   for c in columns_lower)

    if has_date and has_amount and has_desc:
        return "standard"

    # Check for bank statement format (separate debit/credit columns)
    has_debit_col = any(any(kw in c for kw in DEBIT_KEYWORDS) for c in columns_lower)
    has_credit_col = any(any(kw in c for kw in CREDIT_KEYWORDS) for c in columns_lower)

    if has_debit_col and has_credit_col:
        return "bank_statement"

    # Fallback: if we have date + description-like column, try standard
    if has_date and has_desc:
        return "standard"

    return "unknown"


def normalize_bank_statement(df: pd.DataFrame) -> pd.DataFrame:
    """
    Transform bank statement format → standard format.

    Input:  DATE, TRANSACTION DETAILS, WITHDRAWAL AMT, DEPOSIT AMT, [ACCOUNT NO, ...]
    Output: date, amount, description, transaction_type, [account_no]
    """
    normalized = pd.DataFrame()

    # 1. Find and map date column
    date_col = find_column(df, DATE_KEYWORDS, exclude=DATE_EXCLUDE)
    if not date_col:
        # Fallback: content-based detection (find datetime column)
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                date_col = col
                break
    if not date_col:
        raise ValueError("Could not find a date column in the file")
    normalized["date"] = df[date_col]

    # 2. Find and map description column
    desc_col = find_column(df, DESCRIPTION_KEYWORDS)
    if not desc_col:
        # Fallback: find the column with longest average string length (likely description)
        str_cols = df.select_dtypes(include=["object"]).columns
        if len(str_cols) > 0:
            avg_lens = {col: df[col].astype(str).str.len().mean() for col in str_cols}
            desc_col = max(avg_lens, key=avg_lens.get)
        else:
            raise ValueError("Could not find a description column in the file")
    normalized["description"] = df[desc_col]

    # 3. Find debit and credit columns
    debit_col = find_column(df, DEBIT_KEYWORDS, required=False)
    credit_col = find_column(df, CREDIT_KEYWORDS, required=False)

    if not debit_col or not credit_col:
        raise ValueError(
            f"Could not find debit/credit columns. "
            f"Found debit={debit_col}, credit={credit_col}"
        )

    # 4. Merge debit/credit into single amount + transaction_type
    debit_amounts = pd.to_numeric(df[debit_col], errors="coerce").fillna(0)
    credit_amounts = pd.to_numeric(df[credit_col], errors="coerce").fillna(0)

    # Amount is whichever is non-zero
    normalized["amount"] = debit_amounts + credit_amounts

    # Transaction type: debit if withdrawal column had a value, credit if deposit
    normalized["transaction_type"] = "credit"  # default
    normalized.loc[debit_amounts > 0, "transaction_type"] = "debit"

    # 5. Find account number column (optional)
    account_col = find_column(df, ACCOUNT_KEYWORDS, required=False)
    if account_col:
        normalized["account_no"] = df[account_col].astype(str).str.strip().str.rstrip("'")

    return normalized


def detect_and_normalize(df: pd.DataFrame) -> Tuple[pd.DataFrame, str]:
    """
    Auto-detect file format and normalize to standard schema.

    Returns:
        Tuple of (normalized_dataframe, detected_format)
    """
    file_format = detect_format(df)

    if file_format == "standard":
        # Already in standard format, just lowercase column names
        df.columns = df.columns.str.lower().str.strip()
        return df, "standard"

    elif file_format == "bank_statement":
        normalized = normalize_bank_statement(df)
        return normalized, "bank_statement"

    else:
        # Unknown format — try to work with what we have
        # Attempt basic column name normalization and hope for the best
        df.columns = df.columns.str.lower().str.strip()
        return df, "unknown"


# ─── Reference ID Generation ─────────────────────────────────────────────────

def generate_reference_id(row: pd.Series) -> str:
    """Generate a unique reference ID for deduplication based on transaction data."""
    # Include row index to handle multiple identical transactions on same day
    raw = f"{row.name}_{row['date']}_{row['amount']}_{row['description']}"
    return hashlib.md5(raw.encode()).hexdigest()


# ─── Validation ──────────────────────────────────────────────────────────────

def validate_dataframe(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    """
    Validate and clean the normalized dataframe.
    Returns cleaned dataframe and list of validation errors/warnings.
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

    # Drop rows with zero amount (no actual transaction)
    zero_amounts = (df["amount"] == 0).sum()
    if zero_amounts > 0:
        errors.append(f"{zero_amounts} rows have zero amount (dropped)")
        df = df[df["amount"] != 0]

    # Validate descriptions are non-empty (drop null/empty descriptions)
    df["description"] = df["description"].fillna("").astype(str).str.strip()
    invalid_descriptions = (
        (df["description"] == "") |
        (df["description"].str.lower() == "nan") |
        (df["description"].str.lower() == "none") |
        (df["description"].str.lower() == "null")
    )
    empty_count = invalid_descriptions.sum()
    if empty_count > 0:
        errors.append(f"{empty_count} rows have empty/null descriptions (dropped)")
        df = df[~invalid_descriptions]

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


# ─── File Parsers ─────────────────────────────────────────────────────────────

def parse_csv(file_content: bytes) -> pd.DataFrame:
    """Parse CSV file content into a DataFrame."""
    return pd.read_csv(io.BytesIO(file_content))


def parse_json(file_content: bytes) -> pd.DataFrame:
    """Parse JSON file content into a DataFrame."""
    return pd.read_json(io.BytesIO(file_content))


def parse_xlsx(file_content: bytes) -> pd.DataFrame:
    """Parse XLSX file content into a DataFrame."""
    return pd.read_excel(io.BytesIO(file_content), engine="openpyxl")


# ─── Deduplication ────────────────────────────────────────────────────────────

def check_duplicates(db: Session, user_id: int, reference_ids: List[str]) -> set:
    """Check which reference IDs already exist in the database."""
    # Query in batches to avoid SQLite variable limit
    batch_size = 500
    existing = set()
    for i in range(0, len(reference_ids), batch_size):
        batch = reference_ids[i:i + batch_size]
        rows = (
            db.query(Transaction.reference_id)
            .filter(
                Transaction.user_id == user_id,
                Transaction.reference_id.in_(batch),
            )
            .all()
        )
        existing.update(row[0] for row in rows)
    return existing


# ─── Main Pipeline ────────────────────────────────────────────────────────────

def ingest_transactions(
    db: Session,
    user_id: int,
    file_content: bytes,
    filename: str,
    file_type: str,
) -> Dict:
    """
    Main ingestion pipeline: parse, detect format, normalize, validate,
    deduplicate, and store transactions.

    Supports:
    - Standard CSV/JSON (date, amount, description)
    - Bank statement XLSX/CSV (DATE, WITHDRAWAL AMT, DEPOSIT AMT, TRANSACTION DETAILS)

    Returns a summary dict with counts and errors.
    """
    # Stage 1: Parse file based on type
    try:
        if file_type == "csv":
            df = parse_csv(file_content)
        elif file_type == "json":
            df = parse_json(file_content)
        elif file_type in ("xlsx", "xls"):
            df = parse_xlsx(file_content)
        else:
            return {"error": f"Unsupported file type: {file_type}"}
    except Exception as e:
        return {"error": f"Failed to parse file: {str(e)}"}

    total_records = len(df)

    # Stage 2: Detect format and normalize columns
    try:
        df, detected_format = detect_and_normalize(df)
    except ValueError as e:
        return {
            "error": f"Format detection failed: {str(e)}",
            "total_records": total_records,
            "successful": 0,
        }

    # Stage 3: Validate and clean
    # Preserve account_no column before validation (it's not in REQUIRED_COLUMNS)
    has_account_no = "account_no" in df.columns
    account_no_series = df["account_no"].copy() if has_account_no else None

    df, validation_errors = validate_dataframe(df)

    if df.empty and validation_errors:
        return {
            "error": "Validation failed",
            "details": validation_errors,
            "total_records": total_records,
            "successful": 0,
        }

    # Re-attach account_no after validation (rows may have been filtered)
    if has_account_no and account_no_series is not None:
        df["account_no"] = account_no_series.loc[df.index]

    # Stage 4: Deduplicate
    reference_ids = df["reference_id"].tolist()
    existing_refs = check_duplicates(db, user_id, reference_ids)
    duplicates_count = len(df[df["reference_id"].isin(existing_refs)])

    # Filter out duplicates
    df = df[~df["reference_id"].isin(existing_refs)]

    # Stage 5: Bulk insert
    transactions = []
    for _, row in df.iterrows():
        txn = Transaction(
            user_id=user_id,
            date=row["date"],
            amount=row["amount"],
            description=row["description"],
            transaction_type=row["transaction_type"],
            reference_id=row["reference_id"],
            category=row.get("category") if pd.notna(row.get("category", None)) else None,
            source_file=filename,
            account_no=row.get("account_no") if has_account_no and pd.notna(row.get("account_no", None)) else None,
        )
        transactions.append(txn)

    # Bulk insert in batches (better for large files)
    batch_size = 5000
    for i in range(0, len(transactions), batch_size):
        batch = transactions[i:i + batch_size]
        db.bulk_save_objects(batch)
    db.commit()

    return {
        "total_records": total_records,
        "successful": len(transactions),
        "failed": total_records - len(transactions) - duplicates_count,
        "duplicates_skipped": duplicates_count,
        "detected_format": detected_format,
        "validation_errors": validation_errors,
    }
