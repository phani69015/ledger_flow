"""Tests for analytics endpoints."""
import json


def _seed_transactions(client, auth_headers):
    """Helper to seed test transactions."""
    csv_content = (
        "date,amount,description,transaction_type\n"
        "2026-05-01,5000,Monthly Salary January,credit\n"
        "2026-05-02,-45,Starbucks Coffee,debit\n"
        "2026-05-03,-1200,Apartment Rent,debit\n"
        "2026-05-04,-85,Walmart Grocery,debit\n"
        "2026-05-05,-12.99,Netflix Subscription,debit\n"
        "2026-05-06,-55,Shell Gas Station,debit\n"
        "2026-05-07,-150,Amazon Electronics,debit\n"
        "2026-05-08,5000,Monthly Salary February,credit\n"
        "2026-05-09,-35,Uber Ride,debit\n"
        "2026-05-10,-10000,Suspicious Large Transfer,debit\n"
    )
    response = client.post(
        "/api/v1/transactions/upload",
        headers=auth_headers,
        files={"file": ("seed.csv", csv_content.encode(), "text/csv")},
    )
    return response.json()


def test_analytics_summary(client, auth_headers):
    """Test analytics summary endpoint."""
    _seed_transactions(client, auth_headers)

    response = client.get(
        "/api/v1/analytics/summary?days=365",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_transactions"] == 10
    assert data["total_income"] > 0
    assert data["total_expenses"] > 0
    assert "top_categories" in data


def test_category_breakdown(client, auth_headers):
    """Test category breakdown endpoint."""
    _seed_transactions(client, auth_headers)

    response = client.get(
        "/api/v1/analytics/categories?days=365",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    assert "category" in data[0]
    assert "total_amount" in data[0]
    assert "percentage" in data[0]


def test_anomaly_report(client, auth_headers):
    """Test anomaly detection report endpoint."""
    _seed_transactions(client, auth_headers)

    response = client.get(
        "/api/v1/analytics/anomalies",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "total_anomalies" in data
    assert "anomalies" in data
    # The $10,000 transfer should be flagged as anomalous
    assert data["total_anomalies"] >= 1


def test_monthly_trends(client, auth_headers):
    """Test monthly trends endpoint."""
    _seed_transactions(client, auth_headers)

    response = client.get(
        "/api/v1/analytics/trends?months=12",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    assert "month" in data[0]
    assert "income" in data[0]
    assert "expenses" in data[0]
    assert "net" in data[0]


def test_list_transactions(client, auth_headers):
    """Test listing transactions."""
    _seed_transactions(client, auth_headers)

    response = client.get(
        "/api/v1/transactions/",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 10


def test_list_transactions_filter_anomalies(client, auth_headers):
    """Test filtering transactions by anomaly flag."""
    _seed_transactions(client, auth_headers)

    response = client.get(
        "/api/v1/transactions/?anomalies_only=true",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    # Should have at least one anomaly (the $10K transfer)
    assert len(data) >= 1
    assert all(txn["is_anomaly"] for txn in data)


def test_create_single_transaction(client, auth_headers):
    """Test creating a single transaction via API."""
    response = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={
            "date": "2024-06-15T00:00:00Z",
            "amount": 75.50,
            "description": "Starbucks Coffee Meeting",
            "transaction_type": "debit",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["amount"] == 75.50
    assert data["category"] is not None  # Should be auto-categorized
    assert data["category_confidence"] is not None
