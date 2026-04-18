"""Tests for dashboard.py — stats tracking and API handlers."""

import json
import sys
import time
import threading
import urllib.request
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add parent dir to path so we can import dashboard
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dashboard import DashboardStats, check_engine_health
from engines.base import BaseEngine


class TestDashboardStats:
    def test_initial_state(self):
        stats = DashboardStats()
        assert stats.total_searches == 0
        assert stats.recent_queries == []
        assert stats.last_confidence is None

    def test_record_search_updates_count(self):
        stats = DashboardStats()
        stats.record_search("test query", ["exa", "querit"], ["brave"], 0.85, "high", {"exa": 0.3, "querit": 0.2})
        assert stats.total_searches == 1
        assert stats.recent_queries == ["test query"]
        assert stats.last_confidence == "high"
        assert stats.engine_response_times == {"exa": 0.3, "querit": 0.2}

    def test_record_search_keeps_last_20_queries(self):
        stats = DashboardStats()
        for i in range(25):
            stats.record_search(f"q{i}", ["exa"], [], 0.5, "low", {})
        assert len(stats.recent_queries) == 20
        assert stats.recent_queries[0] == "q5"

    def test_record_search_updates_engine_stats(self):
        stats = DashboardStats()
        stats.record_search("q1", ["exa", "querit"], ["brave"], 0.9, "high", {"exa": 0.3, "querit": 0.2})
        assert stats.engine_calls == {"exa": 1, "querit": 1}
        assert stats.engine_failures == {"brave": 1}

    def test_to_dict(self):
        stats = DashboardStats()
        stats.record_search("q1", ["exa"], [], 0.5, "medium", {"exa": 0.3})
        d = stats.to_dict()
        assert d["total_searches"] == 1
        assert d["recent_queries"] == ["q1"]
        assert d["last_confidence"] == "medium"
        assert "exa" in d["engine_calls"]


class TestCheckEngineHealth:
    def test_disabled_engine_returns_disabled(self):
        engine = MagicMock(spec=BaseEngine)
        engine.name = "brave"
        engine.requires_key = True
        engine.is_available.return_value = False

        config = {"engines": {"brave": {"enabled": False, "api_key": ""}}}
        result = check_engine_health(engine, config)
        assert result["status"] == "disabled"

    def test_healthy_engine(self):
        engine = MagicMock(spec=BaseEngine)
        engine.name = "exa"
        engine.requires_key = True
        engine.is_available.return_value = True
        engine.search.return_value = []

        config = {"engines": {"exa": {"enabled": True, "api_key": "key123"}}}
        result = check_engine_health(engine, config)
        assert result["status"] == "healthy"
        assert result["latency_ms"] >= 0

    def test_slow_engine(self):
        engine = MagicMock(spec=BaseEngine)
        engine.name = "slow"
        engine.requires_key = False
        engine.is_available.return_value = True

        def slow_search(*args, **kwargs):
            time.sleep(0.6)
            return []

        engine.search.side_effect = slow_search

        config = {"engines": {"slow": {"enabled": True}}}
        result = check_engine_health(engine, config, slow_threshold=0.5)
        assert result["status"] == "slow"

    def test_error_engine(self):
        engine = MagicMock(spec=BaseEngine)
        engine.name = "broken"
        engine.requires_key = True
        engine.is_available.return_value = True
        engine.search.side_effect = Exception("API error")

        config = {"engines": {"broken": {"enabled": True, "api_key": "key"}}}
        result = check_engine_health(engine, config)
        assert result["status"] == "error"
        assert "API error" in result["error"]


class TestDashboardAPI:
    @classmethod
    def setup_class(cls):
        """Start a test server in a background thread."""
        from dashboard import create_app
        cls.stats = DashboardStats()
        cls.config = {
            "default_engines": ["exa"],
            "min_engines": 1,
            "timeout_seconds": 5,
            "engines": {
                "exa": {"api_key": "fake", "enabled": True, "type": "auto"},
                "brave": {"api_key": "", "enabled": False},
            },
        }
        cls.server = create_app(cls.stats, cls.config, port=0)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.2)

    @classmethod
    def teardown_class(cls):
        cls.server.shutdown()

    def _get(self, path):
        url = f"http://127.0.0.1:{self.port}{path}"
        with urllib.request.urlopen(url, timeout=5) as resp:
            return json.loads(resp.read())

    def test_root_returns_html(self):
        url = f"http://127.0.0.1:{self.port}/"
        with urllib.request.urlopen(url, timeout=5) as resp:
            content_type = resp.headers.get("Content-Type", "")
            assert "text/html" in content_type

    def test_stats_endpoint(self):
        data = self._get("/api/stats")
        assert "total_searches" in data
        assert "recent_queries" in data

    def test_health_endpoint(self):
        # Mock engine discovery to avoid real network calls
        mock_exa = MagicMock(spec=BaseEngine)
        mock_exa.name = "exa"
        mock_exa.display_name = "Exa AI"
        mock_exa.is_available.return_value = True
        mock_exa.search.return_value = []

        mock_brave = MagicMock(spec=BaseEngine)
        mock_brave.name = "brave"
        mock_brave.display_name = "Brave Search"
        mock_brave.is_available.return_value = False

        with patch("dispatcher._discover_engine_classes", return_value=[]), \
             patch("dispatcher._instantiate_engines", return_value=[mock_exa, mock_brave]):
            data = self._get("/api/health")
            assert isinstance(data, list)
            names = [e["name"] for e in data]
            assert "exa" in names
            assert "brave" in names
