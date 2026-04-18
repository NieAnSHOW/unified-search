"""Unit tests for the Tavily search engine implementation."""

import pytest
from engines.tavily import TavilyEngine


class TestTavilyEngineAvailability:
    """Test engine availability checks."""

    def test_is_available_with_valid_key(self):
        """Engine should be available when API key is present."""
        engine = TavilyEngine()
        config = {"api_key": "tvly-test123"}
        assert engine.is_available(config) is True

    def test_is_available_with_empty_key(self):
        """Engine should not be available when API key is empty."""
        engine = TavilyEngine()
        config = {"api_key": ""}
        assert engine.is_available(config) is False

    def test_is_available_with_missing_key(self):
        """Engine should not be available when API key is missing."""
        engine = TavilyEngine()
        config = {}
        assert engine.is_available(config) is False

    def test_is_available_with_whitespace_key(self):
        """Engine should not be available when API key is only whitespace."""
        engine = TavilyEngine()
        config = {"api_key": "   "}
        assert engine.is_available(config) is False


class TestTavilyEngineRequestBuilding:
    """Test request body construction."""

    def test_build_request_body_basic(self):
        """Should build basic request body with default settings."""
        body = TavilyEngine._build_request_body(
            query="test query",
            max_results=10,
            freshness=None,
            config=None,
        )
        assert body["query"] == "test query"
        assert body["max_results"] == 10
        assert body["search_depth"] == "basic"
        assert body["include_answer"] is False
        assert body["include_raw_content"] is False
        assert "start_date" not in body

    def test_build_request_body_with_freshness_pw(self):
        """Should include start_date when freshness is pw (past week)."""
        body = TavilyEngine._build_request_body(
            query="test query",
            max_results=10,
            freshness="pw",
            config=None,
        )
        assert "start_date" in body
        # Verify date format: YYYY-MM-DD
        from datetime import datetime
        datetime.strptime(body["start_date"], "%Y-%m-%d")  # Should not raise

    def test_build_request_body_with_custom_config(self):
        """Should respect custom config settings."""
        body = TavilyEngine._build_request_body(
            query="test query",
            max_results=10,
            freshness=None,
            config={"search_depth": "advanced", "include_answer": True},
        )
        assert body["search_depth"] == "advanced"
        assert body["include_answer"] is True


class TestTavilyEngineNormalization:
    """Test result normalization."""

    def test_normalize_typical_response(self):
        """Should normalize typical Tavily response correctly."""
        engine = TavilyEngine()
        raw_results = [
            {
                "title": "Test Title",
                "url": "https://example.com",
                "content": "Test snippet content",
                "score": 0.95,
                "published_date": "2026-04-01",
            }
        ]
        results = engine._normalize(raw_results)

        assert len(results) == 1
        assert results[0].title == "Test Title"
        assert results[0].url == "https://example.com"
        assert results[0].snippet == "Test snippet content"
        assert results[0].source_engine == ["tavily"]
        assert results[0].published_date == "2026-04-01"
        assert results[0].score == 0.95

    def test_normalize_empty_results(self):
        """Should handle empty results list."""
        engine = TavilyEngine()
        results = engine._normalize([])
        assert len(results) == 0

    def test_normalize_missing_fields(self):
        """Should handle missing optional fields gracefully."""
        engine = TavilyEngine()
        raw_results = [
            {
                "title": "Test Title",
                "url": "https://example.com",
                # Missing content, score, published_date
            }
        ]
        results = engine._normalize(raw_results)

        assert len(results) == 1
        assert results[0].snippet == ""
        assert results[0].score == 0.0
        assert results[0].published_date is None

    def test_normalize_multiple_results(self):
        """Should normalize multiple results in order."""
        engine = TavilyEngine()
        raw_results = [
            {"title": "First", "url": "https://first.com", "content": "First content", "score": 0.9},
            {"title": "Second", "url": "https://second.com", "content": "Second content", "score": 0.8},
        ]
        results = engine._normalize(raw_results)

        assert len(results) == 2
        assert results[0].title == "First"
        assert results[1].title == "Second"
