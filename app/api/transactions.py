from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models.user import User
from app.models.transaction import Transaction
from app.schemas.transaction import (
    TransactionCreate,
    TransactionResponse,
    TransactionUpdate,
    UploadResponse,
)
from app.api.deps import get_current_user
from app.services.ingestion import ingest_transactions
from app.services.categorization import categorize_transaction
from app.services.anomaly_detection import run_anomaly_detection_for_user

router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.post("/upload", response_model=UploadResponse)
async def upload_transactions(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a CSV or JSON file containing financial transactions.
    The pipeline will:
    1. Parse and validate the file
    2. Deduplicate against existing records
    3. Auto-categorize transactions using AI
    4. Run anomaly detection
    5. Store processed transactions
    """
    # Validate file type
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    file_ext = file.filename.rsplit(".", 1)[-1].lower()
    if file_ext not in ("csv", "json"):
        raise HTTPException(
            status_code=400,
            detail="Only CSV and JSON files are supported",
        )

    # Read file content
    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="File is empty")

    # Run ingestion pipeline
    result = ingest_transactions(
        db=db,
        user_id=current_user.id,
        file_content=content,
        filename=file.filename,
        file_type=file_ext,
    )

    if "error" in result:
        raise HTTPException(status_code=422, detail=result)

    # Run AI categorization on newly ingested transactions
    uncategorized = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == current_user.id,
            Transaction.category.is_(None),
        )
        .all()
    )

    categories_assigned = 0
    for txn in uncategorized:
        category, confidence = categorize_transaction(txn.description, txn.amount)
        txn.category = category
        txn.category_confidence = confidence
        categories_assigned += 1

    db.commit()

    # Run anomaly detection
    anomaly_result = run_anomaly_detection_for_user(db, current_user.id)

    return UploadResponse(
        filename=file.filename,
        total_records=result["total_records"],
        successful=result["successful"],
        failed=result["failed"],
        duplicates_skipped=result["duplicates_skipped"],
        anomalies_detected=anomaly_result.get("anomalies_found", 0),
        categories_assigned=categories_assigned,
        message=f"Successfully processed {result['successful']} transactions from {file.filename}",
    )


@router.post("/", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def create_transaction(
    txn_data: TransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a single transaction manually."""
    # Auto-categorize if no category provided
    category = txn_data.category
    confidence = None
    if not category:
        category, confidence = categorize_transaction(txn_data.description, txn_data.amount)

    txn = Transaction(
        user_id=current_user.id,
        date=txn_data.date,
        amount=abs(txn_data.amount),
        description=txn_data.description,
        transaction_type=txn_data.transaction_type,
        reference_id=txn_data.reference_id,
        category=category,
        category_confidence=confidence,
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)

    return txn


@router.get("/", response_model=List[TransactionResponse])
def list_transactions(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    category: Optional[str] = None,
    transaction_type: Optional[str] = None,
    anomalies_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List transactions with optional filtering."""
    query = db.query(Transaction).filter(Transaction.user_id == current_user.id)

    if category:
        query = query.filter(Transaction.category == category)
    if transaction_type:
        query = query.filter(Transaction.transaction_type == transaction_type)
    if anomalies_only:
        query = query.filter(Transaction.is_anomaly == True)

    transactions = query.order_by(Transaction.date.desc()).offset(skip).limit(limit).all()
    return transactions


@router.get("/{transaction_id}", response_model=TransactionResponse)
def get_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific transaction by ID."""
    txn = (
        db.query(Transaction)
        .filter(Transaction.id == transaction_id, Transaction.user_id == current_user.id)
        .first()
    )
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return txn


@router.put("/{transaction_id}", response_model=TransactionResponse)
def update_transaction(
    transaction_id: int,
    txn_data: TransactionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a transaction's category or details."""
    txn = (
        db.query(Transaction)
        .filter(Transaction.id == transaction_id, Transaction.user_id == current_user.id)
        .first()
    )
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")

    if txn_data.category is not None:
        txn.category = txn_data.category
        txn.category_confidence = 1.0  # User-assigned = 100% confidence
    if txn_data.description is not None:
        txn.description = txn_data.description
    if txn_data.transaction_type is not None:
        txn.transaction_type = txn_data.transaction_type

    db.commit()
    db.refresh(txn)
    return txn


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a transaction."""
    txn = (
        db.query(Transaction)
        .filter(Transaction.id == transaction_id, Transaction.user_id == current_user.id)
        .first()
    )
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")

    db.delete(txn)
    db.commit()


@router.post("/detect-anomalies")
def trigger_anomaly_detection(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually trigger anomaly detection on all user transactions."""
    result = run_anomaly_detection_for_user(db, current_user.id)
    return result
