"""Tests for authentication endpoints"""
from app.api.auth import (
    hash_password, verify_password, create_signed_token,
    verify_signed_token, _login_attempts
)


class TestPasswordHashing:
    def test_hash_and_verify(self):
        pw = "miPassword123"
        hashed = hash_password(pw)
        assert verify_password(pw, hashed)

    def test_wrong_password_fails(self):
        hashed = hash_password("correcta")
        assert not verify_password("incorrecta", hashed)

    def test_hash_format(self):
        hashed = hash_password("test")
        assert "$" in hashed  # salt$hash format

    def test_different_hashes_for_same_password(self):
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2  # different salts


class TestTokens:
    def test_create_and_verify(self):
        token = create_signed_token("user1", "admin")
        result = verify_signed_token(token)
        assert result is not None
        assert result["username"] == "user1"
        assert result["role"] == "admin"

    def test_invalid_token(self):
        assert verify_signed_token("invalid-token") is None

    def test_none_token(self):
        assert verify_signed_token(None) is None

    def test_empty_token(self):
        assert verify_signed_token("") is None


class TestLoginEndpoint:
    def setup_method(self):
        _login_attempts.clear()

    def test_login_superadmin(self, client):
        resp = client.post("/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "session_token" in resp.cookies

    def test_login_wrong_password(self, client):
        resp = client.post("/api/auth/login", json={
            "username": "admin",
            "password": "wrongpass"
        })
        assert resp.status_code == 401

    def test_login_wrong_username(self, client):
        resp = client.post("/api/auth/login", json={
            "username": "nonexistent",
            "password": "admin123"
        })
        assert resp.status_code == 401


class TestAuthCheck:
    def test_check_authenticated(self, admin_client):
        resp = admin_client.get("/api/auth/check")
        assert resp.status_code == 200
        data = resp.json()
        assert data["authenticated"] is True
        assert data["username"] == "admin"
        assert data["role"] == "admin"

    def test_check_unauthenticated(self, client):
        resp = client.get("/api/auth/check")
        assert resp.status_code == 200
        data = resp.json()
        assert data["authenticated"] is False

    def test_check_regular_user(self, user_client):
        resp = user_client.get("/api/auth/check")
        assert resp.status_code == 200
        data = resp.json()
        assert data["authenticated"] is True
        assert data["role"] == "user"


class TestLogout:
    def test_logout(self, admin_client):
        resp = admin_client.post("/api/auth/logout")
        assert resp.status_code == 200
        assert resp.json()["success"] is True


class TestProtectedEndpoints:
    def test_unauthenticated_access(self, client):
        resp = client.get("/api/chat/usage")
        assert resp.status_code == 401

    def test_unauthenticated_admin_access(self, client):
        resp = client.get("/api/admin/stats")
        assert resp.status_code == 401

    def test_non_admin_access_to_admin(self, user_client):
        resp = user_client.get("/api/admin/stats")
        assert resp.status_code == 403
