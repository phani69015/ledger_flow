"""Tests for ingestion and categorization services."""
import os
import pytest
from app.services.categorization import categorize_transaction, categorize_batch
from app.services.ingestion import validate_dataframe, parse_csv
import pandas as pd


def test_categorize_food_transaction():
    """Test food & dining categorization."""
    category, confidence = categorize_transaction("Starbucks Coffee Morning")
    assert category == "Food & Dining"
    assert confidence > 0.5


def test_categorize_transport_transaction():
    """Test transportation categorization."""
    category, confidence = categorize_transaction("Uber Ride Downtown")
    assert category == "Transportation"
    assert confidence > 0.4


def test_categorize_salary_transaction():
    """Test salary/income categorization."""
    category, confidence = categorize_transaction("Monthly Salary Payment")
    assert category == "Salary & Income"
    assert confidence >= 0.5


def test_categorize_entertainment():
    """Test entertainment categorization."""
    category, confidence = categorize_transaction("Netflix Monthly Subscription")
    assert category == "Entertainment"
    assert confidence > 0.5


def test_categorize_unknown_returns_uncategorized():
    """Test unknown description returns Uncategorized."""
    category, confidence = categorize_transaction("XYZABC123 Random String")
    assert category == "Uncategorized"
    assert confidence == 0.0


def test_categorize_batch():
    """Test batch categorization."""
    transactions = [
        {"description": "Walmart Grocery Shopping", "amount": 85.30},
        {"description": "Netflix Subscription", "amount": 12.99},
        {"description": "Monthly Salary", "amount": 5200.00},
    ]
    results = categorize_batch(transactions)
    assert len(results) == 3
    assert results[0]["category"] == "Shopping"
    assert results[1]["category"] == "Entertainment"
    assert results[2]["category"] == "Salary & Income"
    assert all("category_confidence" in r for r in results)


def test_validate_dataframe_valid():
    """Test validation with valid data."""
    df = pd.DataFrame({
        "date": ["2024-01-01", "2024-01-02"],
        "amount": [100.0, -50.0],
        "description": ["Salary", "Coffee"],
    })
    result_df, errors = validate_dataframe(df)
    assert len(result_df) == 2
    assert len(errors) == 0


def test_validate_dataframe_missing_columns():
    """Test validation with missing required columns."""
    df = pd.DataFrame({
        "date": ["2024-01-01"],
        "price": [100.0],  # wrong column name
    })
    result_df, errors = validate_dataframe(df)
    assert len(result_df) == 0
    assert len(errors) > 0


def test_csv_upload(client, auth_headers):
    """Test CSV file upload endpoint."""
    csv_content = (
        "date,amount,description,transaction_type\n"
        "2024-01-01,5000,Monthly Salary,credit\n"
        "2024-01-02,-45,Starbucks Coffee,debit\n"
        "2024-01-03,-1200,Rent Payment,debit\n"
    )

    response = client.post(
        "/api/v1/transactions/upload",
        headers=auth_headers,
        files={"file": ("test.csv", csv_content.encode(), "text/csv")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_records"] == 3
    assert data["successful"] == 3
    assert data["categories_assigned"] > 0


def test_json_upload(client, auth_headers):
    """Test JSON file upload endpoint."""
    import json

    json_content = json.dumps([
        {
            "date": "2024-03-01T00:00:00Z",
            "amount": 5500.00,
            "description": "Freelance Payment",
            "transaction_type": "credit",
        },
        {
            "date": "2024-03-02T00:00:00Z",
            "amount": -200.00,
            "description": "Amazon Shopping",
            "transaction_type": "debit",
        },
    ])

    response = client.post(
        "/api/v1/transactions/upload",
        headers=auth_headers,
        files={"file": ("test.json", json_content.encode(), "application/json")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_records"] == 2
    assert data["successful"] == 2
