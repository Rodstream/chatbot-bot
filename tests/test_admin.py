"""Tests for admin and documents endpoints"""
from unittest.mock import MagicMock, patch
from app.services.search_service import (
    _cache, _extract_keywords, cache_clear, cache_stats,
    _cache_set, _cache_get
)


class TestAdminStats:
    def test_requires_admin(self, user_client):
        resp = user_client.get("/api/admin/stats")
        assert resp.status_code == 403

    def test_requires_auth(self, client):
        resp = client.get("/api/admin/stats")
        assert resp.status_code == 401

    def test_stats_with_mock(self, admin_client, mock_supabase):
        # Mock the table queries
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table

        mock_select = MagicMock()
        mock_table.select.return_value = mock_select
        mock_select.execute.return_value = MagicMock(data=[])

        resp = admin_client.get("/api/admin/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "stats" in data


class TestCacheClear:
    def test_requires_admin(self, user_client):
        resp = user_client.post("/api/admin/cache/clear")
        assert resp.status_code == 403

    def test_clear_cache(self, admin_client):
        # Seed cache
        _cache_set("test query", "response", [], 1)
        assert len(_cache) > 0

        resp = admin_client.post("/api/admin/cache/clear")
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert len(_cache) == 0


class TestCacheLogic:
    def setup_method(self):
        cache_clear()

    def test_cache_set_and_get(self):
        _cache_set("hello world", "response text", [{"source": "doc.pdf"}], 1)
        result = _cache_get("hello world")
        assert result is not None
        assert result["response"] == "response text"

    def test_cache_normalized_key(self):
        _cache_set("Hello   World", "resp", [], 1)
        result = _cache_get("hello world")
        assert result is not None

    def test_cache_miss(self):
        result = _cache_get("nonexistent")
        assert result is None

    def test_cache_stats(self):
        stats = cache_stats()
        assert "entries" in stats
        assert "hits" in stats
        assert "misses" in stats


class TestReranking:
    def test_extract_keywords(self):
        kw = _extract_keywords("Como se hace la señalizacion vial")
        assert "hace" in kw
        assert "la" not in kw  # stopword
        assert "se" not in kw  # stopword

    def test_extract_keywords_empty(self):
        kw = _extract_keywords("")
        assert len(kw) == 0

    def test_extract_keywords_short_words_filtered(self):
        kw = _extract_keywords("a en de lo si")
        assert len(kw) == 0  # all stopwords or <=2 chars

    def test_rerank_basic(self):
        from app.services.search_service import SearchService
        ss = SearchService()

        docs = [
            {"content": "compras y licitaciones empresa", "similarity": 0.9, "source": "a.pdf", "page_number": 1},
            {"content": "señalizacion vial en rutas nacionales", "similarity": 0.7, "source": "b.pdf", "page_number": 1},
        ]
        result = ss._rerank("señalizacion vial", docs, 2)
        # b.pdf should rank higher due to keyword overlap despite lower similarity
        assert result[0]["source"] == "b.pdf"

    def test_rerank_deduplicates(self):
        from app.services.search_service import SearchService
        ss = SearchService()

        docs = [
            {"content": "señalizacion vial parte 1", "similarity": 0.8, "source": "doc.pdf", "page_number": 1},
            {"content": "señalizacion vial parte 2", "similarity": 0.75, "source": "doc.pdf", "page_number": 1},
            {"content": "otro tema diferente aqui", "similarity": 0.6, "source": "other.pdf", "page_number": 2},
        ]
        result = ss._rerank("señalizacion vial", docs, 3)
        # Should deduplicate same source+page
        sources = [(d["source"], d["page_number"]) for d in result]
        assert len(sources) == len(set(sources))


class TestDocumentsFilters:
    def test_requires_auth(self, client):
        resp = client.get("/api/documents/filters")
        assert resp.status_code == 401

    def test_filters_with_mock(self, admin_client, mock_supabase):
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_select = MagicMock()
        mock_table.select.return_value = mock_select
        mock_select.execute.return_value = MagicMock(data=[
            {"document_type": "procedimiento", "obra": "Ruta 9"},
            {"document_type": "parte_diario", "obra": "Ruta 9"},
            {"document_type": "procedimiento", "obra": "Autopista"},
        ])

        resp = admin_client.get("/api/documents/filters")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "parte_diario" in data["document_types"]
        assert "procedimiento" in data["document_types"]
        assert "Autopista" in data["obras"]
        assert "Ruta 9" in data["obras"]


class TestDocumentsSources:
    def test_requires_auth(self, client):
        resp = client.get("/api/documents/sources")
        assert resp.status_code == 401

    def test_sources_with_mock(self, admin_client, mock_supabase):
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_select = MagicMock()
        mock_table.select.return_value = mock_select
        mock_select.execute.return_value = MagicMock(data=[
            {"source": "manual.pdf", "uploaded_by": "admin"},
            {"source": "manual.pdf", "uploaded_by": "admin"},
            {"source": "guia.docx", "uploaded_by": "user1"},
        ])

        resp = admin_client.get("/api/documents/sources")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["count"] == 2  # deduplicated


class TestHealthEndpoint:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"
