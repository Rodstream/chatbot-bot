"""Tests for chat endpoints and usage tracking"""
from app.api.chat import (
    get_user_usage, record_usage, _daily_usage
)


class TestUsageTracking:
    def setup_method(self):
        _daily_usage.clear()

    def test_initial_usage_is_zero(self):
        assert get_user_usage("newuser") == 0

    def test_record_increments(self):
        record_usage("testuser")
        assert get_user_usage("testuser") == 1
        record_usage("testuser")
        assert get_user_usage("testuser") == 2

    def test_separate_users(self):
        record_usage("user1")
        record_usage("user1")
        record_usage("user2")
        assert get_user_usage("user1") == 2
        assert get_user_usage("user2") == 1


class TestUsageEndpoint:
    def setup_method(self):
        _daily_usage.clear()

    def test_usage_unlimited(self, admin_client):
        resp = admin_client.get("/api/chat/usage")
        assert resp.status_code == 200
        data = resp.json()
        assert data["unlimited"] is True

    def test_usage_regular_user(self, user_client):
        resp = user_client.get("/api/chat/usage")
        assert resp.status_code == 200
        data = resp.json()
        # DAILY_MESSAGE_LIMIT is 0 (unlimited) by default
        assert data["unlimited"] is True

    def test_unauthenticated(self, client):
        resp = client.get("/api/chat/usage")
        assert resp.status_code == 401


class TestStreamEndpoint:
    def test_stream_requires_auth(self, client):
        resp = client.post("/api/chat/stream", json={
            "query": "test",
            "limit": 5,
            "similarity_threshold": 0.2
        })
        assert resp.status_code == 401

    def test_stream_validates_input(self, admin_client):
        # Empty query should still be accepted (validated downstream)
        resp = admin_client.post("/api/chat/stream", json={
            "query": "",
            "limit": 5,
            "similarity_threshold": 0.2
        })
        # Should get a response (might be error from search service, but not 422)
        assert resp.status_code in (200, 500)
