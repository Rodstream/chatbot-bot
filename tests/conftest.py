"""Shared fixtures for tests"""
import os
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

# Set test env vars before importing app
os.environ["SESSION_SECRET"] = "test-secret-key-for-testing"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ENVIRONMENT"] = "development"

from app.api.auth import hash_password

os.environ["ADMIN_PASSWORD_HASH"] = hash_password("admin123")

from app.main import app


@pytest.fixture
def client():
    """Unauthenticated test client"""
    return TestClient(app)


@pytest.fixture
def admin_client(client):
    """Test client authenticated as admin"""
    resp = client.post("/api/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    assert resp.status_code == 200
    # TestClient automatically handles cookies
    return client


@pytest.fixture
def user_token():
    """Create a signed token for a regular user (no Supabase needed)"""
    from app.api.auth import create_signed_token
    return create_signed_token("testuser", "user")


@pytest.fixture
def mock_supabase():
    """Mock supabase client for tests that need DB"""
    mock_client = MagicMock()
    with patch("app.services.supabase_service.supabase_service.get_client", return_value=mock_client):
        yield mock_client


@pytest.fixture
def user_client(client, user_token, mock_supabase):
    """Test client authenticated as regular user.

    Depends on mock_supabase so get_current_user's existence check (which
    queries the real users table for non-superadmin usernames) doesn't hit
    the actual configured Supabase project looking for a "testuser" that
    was never created there.
    """
    client.cookies.set("session_token", user_token)
    return client
