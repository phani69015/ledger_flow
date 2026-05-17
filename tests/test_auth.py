"""Tests for authentication endpoints."""


def test_register_user(client):
    """Test user registration."""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "newuser@example.com",
            "username": "newuser",
            "password": "password123",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newuser@example.com"
    assert data["username"] == "newuser"
    assert "hashed_password" not in data


def test_register_duplicate_email(client):
    """Test registration with duplicate email fails."""
    user_data = {
        "email": "duplicate@example.com",
        "username": "user1",
        "password": "password123",
    }
    client.post("/api/v1/auth/register", json=user_data)

    # Try to register again with same email
    user_data["username"] = "user2"
    response = client.post("/api/v1/auth/register", json=user_data)
    assert response.status_code == 400
    assert "already registered" in response.json()["detail"]


def test_login_success(client):
    """Test successful login returns JWT token."""
    # Register first
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "login@example.com",
            "username": "loginuser",
            "password": "password123",
        },
    )

    # Login
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "login@example.com",
            "password": "password123",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_invalid_credentials(client):
    """Test login with wrong password fails."""
    # Register first
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "wrongpass@example.com",
            "username": "wronguser",
            "password": "correctpass",
        },
    )

    # Try login with wrong password
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "wrongpass@example.com",
            "password": "wrongpassword",
        },
    )
    assert response.status_code == 401


def test_get_current_user(client, auth_headers):
    """Test getting current user info with valid token."""
    response = client.get("/api/v1/auth/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["username"] == "testuser"


def test_protected_route_without_token(client):
    """Test accessing protected route without token fails."""
    response = client.get("/api/v1/auth/me")
    assert response.status_code in (401, 403)
