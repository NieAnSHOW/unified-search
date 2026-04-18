"""Tests for Querit search engine."""

import json
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError


def _make_response(data: dict, status: int = 200):
    """Create a mock HTTP response with JSON body."""
    response = MagicMock()
    response.status = status
    response.read.return_value = json.dumps(data).encode("utf-8")
    response.__enter__ = lambda self: self
    response.__exit__ = lambda self, *args: None
    return response


def _sample_querit_response():
    """Return a sample Querit API response with multiple results."""
    return {
        "results": {
            "result": [
                {
                    "url": "https://example.com/1",
                    "title": "First Result",
                    "snippet": "Snippet for the first result.",
                    "page_age": "2025-04-01",
                    "site_name": "example.com",
                },
                {
                    "url": "https://example.com/2",
                    "title": "Second Result",
                    "snippet": "Snippet for the second result.",
                    "page_age": "2025-03-20",
                    "site_name": "example.com",
                },
                {
                    "url": "https://example.com/3",
                    "title": "Third Result",
                    "snippet": "Snippet for the third result.",
                    "page_age": "2025-01-15",
                    "site_name": "example.com",
                },
            ]
        }
    }


class TestQueritAttributes(unittest.TestCase):
    """Test Querit engine class attributes."""

    def _get_engine(self):
        from engines.querit import QueritEngine
        return QueritEngine

    def test_name(self):
        """QueritEngine.name is 'querit'."""
        engine = self._get_engine()()
        self.assertEqual(engine.name, "querit")

    def test_display_name(self):
        """QueritEngine.display_name is 'Querit'."""
        engine = self._get_engine()()
        self.assertEqual(engine.display_name, "Querit")

    def test_priority(self):
        """QueritEngine.priority is 2."""
        engine = self._get_engine()()
        self.assertEqual(engine.priority, 2)

    def test_requires_key(self):
        """QueritEngine.requires_key is True."""
        engine = self._get_engine()()
        self.assertTrue(engine.requires_key)


class TestQueritSearch(unittest.TestCase):
    """Test QueritEngine.search() method."""

    def _get_engine(self):
        from engines.querit import QueritEngine
        return QueritEngine

    @patch("engines.querit.urlopen")
    def test_search_returns_results(self, mock_urlopen):
        """search() returns list of SearchResult on successful API response."""
        mock_urlopen.return_value = _make_response(_sample_querit_response())
        engine = self._get_engine()()
        config = {"api_key": "test-key"}

        results = engine.search("test query", max_results=10, config=config)

        self.assertEqual(len(results), 3)
        self.assertEqual(results[0].title, "First Result")
        self.assertEqual(results[0].url, "https://example.com/1")
        self.assertEqual(results[0].snippet, "Snippet for the first result.")

    @patch("engines.querit.urlopen")
    def test_search_sends_correct_request(self, mock_urlopen):
        """search() sends POST with correct endpoint, auth, and body."""
        mock_urlopen.return_value = _make_response(_sample_querit_response())
        engine = self._get_engine()()
        config = {"api_key": "my-secret-key"}

        engine.search("hello world", max_results=5, config=config)

        mock_urlopen.assert_called_once()
        call_args = mock_urlopen.call_args
        request = call_args[0][0]

        self.assertEqual(request.method, "POST")
        self.assertEqual(request.full_url, "https://api.querit.ai/v1/search")
        # Check Authorization header
        self.assertIn("Authorization", request.headers)
        self.assertEqual(request.headers["Authorization"], "Bearer my-secret-key")
        # Check request body
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(body["query"], "hello world")
        self.assertEqual(body["count"], 5)

    @patch("engines.querit.urlopen")
    def test_search_no_config_raises(self, mock_urlopen):
        """search() raises ValueError when no config or api_key is provided."""
        engine = self._get_engine()()

        with self.assertRaises(ValueError) as ctx:
            engine.search("test query")
        self.assertIn("api_key", str(ctx.exception))

    @patch("engines.querit.urlopen")
    def test_search_empty_api_key_raises(self, mock_urlopen):
        """search() raises ValueError when api_key is empty string."""
        engine = self._get_engine()()

        with self.assertRaises(ValueError) as ctx:
            engine.search("test query", config={"api_key": ""})
        self.assertIn("api_key", str(ctx.exception))

    @patch("engines.querit.urlopen")
    def test_search_api_error_raises(self, mock_urlopen):
        """search() raises RuntimeError when API returns HTTP error."""
        mock_urlopen.side_effect = HTTPError(
            url="https://api.querit.ai/v1/search",
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=None,
        )
        engine = self._get_engine()()
        config = {"api_key": "bad-key"}

        with self.assertRaises(RuntimeError) as ctx:
            engine.search("test query", config=config)
        self.assertIn("Querit API error", str(ctx.exception))
        self.assertIn("401", str(ctx.exception))

    @patch("engines.querit.urlopen")
    def test_search_network_error_raises(self, mock_urlopen):
        """search() raises RuntimeError on network failure."""
        mock_urlopen.side_effect = URLError("Connection refused")
        engine = self._get_engine()()
        config = {"api_key": "test-key"}

        with self.assertRaises(RuntimeError) as ctx:
            engine.search("test query", config=config)
        self.assertIn("Querit API request failed", str(ctx.exception))

    @patch("engines.querit.urlopen")
    def test_search_empty_results(self, mock_urlopen):
        """search() returns empty list when API returns no results."""
        mock_urlopen.return_value = _make_response({"results": {"result": []}})
        engine = self._get_engine()()
        config = {"api_key": "test-key"}

        results = engine.search("obscure query", config=config)

        self.assertEqual(results, [])

    @patch("engines.querit.urlopen")
    def test_search_missing_results_key(self, mock_urlopen):
        """search() returns empty list when API response has no results key."""
        mock_urlopen.return_value = _make_response({"status": "ok"})
        engine = self._get_engine()()
        config = {"api_key": "test-key"}

        results = engine.search("test query", config=config)

        self.assertEqual(results, [])


class TestQueritNormalize(unittest.TestCase):
    """Test QueritEngine._normalize() field mapping."""

    def _get_engine(self):
        from engines.querit import QueritEngine
        return QueritEngine

    def test_field_mapping(self):
        """_normalize correctly maps url, title, snippet, page_age."""
        engine = self._get_engine()()
        raw = _sample_querit_response()["results"]["result"]

        results = engine._normalize(raw)

        self.assertEqual(len(results), 3)
        self.assertEqual(results[0].title, "First Result")
        self.assertEqual(results[0].url, "https://example.com/1")
        self.assertEqual(results[0].snippet, "Snippet for the first result.")
        self.assertEqual(results[0].published_date, "2025-04-01")
        self.assertEqual(results[1].published_date, "2025-03-20")
        self.assertEqual(results[2].published_date, "2025-01-15")

    def test_source_engine(self):
        """_normalize sets source_engine to ['querit'] for all results."""
        engine = self._get_engine()()
        raw = _sample_querit_response()["results"]["result"]

        results = engine._normalize(raw)

        for r in results:
            self.assertEqual(r.source_engine, ["querit"])

    def test_score_rank_decay(self):
        """_normalize uses 1/(index+1) as score for rank decay."""
        engine = self._get_engine()()
        raw = _sample_querit_response()["results"]["result"]

        results = engine._normalize(raw)

        self.assertAlmostEqual(results[0].score, 1.0)
        self.assertAlmostEqual(results[1].score, 0.5)
        self.assertAlmostEqual(results[2].score, 1.0 / 3.0)

    def test_page_age_missing(self):
        """_normalize sets published_date to None when page_age is absent."""
        engine = self._get_engine()()
        raw = [
            {
                "url": "https://example.com/no-age",
                "title": "No Age",
                "snippet": "No page_age field.",
            }
        ]

        results = engine._normalize(raw)

        self.assertEqual(len(results), 1)
        self.assertIsNone(results[0].published_date)

    def test_empty_raw_list(self):
        """_normalize returns empty list for empty input."""
        engine = self._get_engine()()

        results = engine._normalize([])

        self.assertEqual(results, [])


class TestQueritFreshnessFilter(unittest.TestCase):
    """Test freshness post-filtering via page_age."""

    def _get_engine(self):
        from engines.querit import QueritEngine
        return QueritEngine

    def _build_results(self, days_ago_list):
        """Build raw results list with page_age set to N days ago."""
        today = datetime.now()
        raw = []
        for days in days_ago_list:
            date = (today - timedelta(days=days)).strftime("%Y-%m-%d")
            raw.append({
                "url": f"https://example.com/{days}d",
                "title": f"Result {days} days ago",
                "snippet": f"Snippet {days}",
                "page_age": date,
            })
        return raw

    def test_freshness_pd_filters_old_results(self):
        """freshness='pd' keeps only results from the past 1 day."""
        engine = self._get_engine()()
        raw = self._build_results([0, 1, 3])

        results = engine._normalize(raw, freshness="pd")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Result 0 days ago")

    def test_freshness_pw_filters_old_results(self):
        """freshness='pw' keeps only results from the past 7 days."""
        engine = self._get_engine()()
        raw = self._build_results([3, 7, 14])

        results = engine._normalize(raw, freshness="pw")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Result 3 days ago")

    def test_freshness_pm_filters_old_results(self):
        """freshness='pm' keeps only results from the past 30 days."""
        engine = self._get_engine()()
        raw = self._build_results([10, 30, 45])

        results = engine._normalize(raw, freshness="pm")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Result 10 days ago")

    def test_freshness_none_keeps_all(self):
        """freshness=None keeps all results."""
        engine = self._get_engine()()
        raw = self._build_results([0, 100, 365])

        results = engine._normalize(raw, freshness=None)

        self.assertEqual(len(results), 3)

    def test_freshness_unknown_keeps_all(self):
        """Unknown freshness value keeps all results (no filtering)."""
        engine = self._get_engine()()
        raw = self._build_results([0, 100])

        results = engine._normalize(raw, freshness="unknown")

        self.assertEqual(len(results), 2)

    def test_freshness_no_page_age_keeps_result(self):
        """Results without page_age are kept when freshness filter is active."""
        engine = self._get_engine()()
        raw = [
            {
                "url": "https://example.com/no-age",
                "title": "No Age",
                "snippet": "No page_age.",
            }
        ]

        results = engine._normalize(raw, freshness="pd")

        self.assertEqual(len(results), 1)
        self.assertIsNone(results[0].published_date)

    def test_freshness_score_recalculated_after_filter(self):
        """Scores are recalculated based on position after filtering."""
        engine = self._get_engine()()
        # 3 results, freshness pd will keep only first (0 days ago)
        raw = self._build_results([0, 5, 10])

        results = engine._normalize(raw, freshness="pd")

        self.assertEqual(len(results), 1)
        self.assertAlmostEqual(results[0].score, 1.0)


class TestQueritIsAvailable(unittest.TestCase):
    """Test QueritEngine.is_available inherited from BaseEngine."""

    def test_available_with_key(self):
        """is_available returns True when api_key is present."""
        from engines.querit import QueritEngine
        engine = QueritEngine()
        self.assertTrue(engine.is_available({"api_key": "my-key"}))

    def test_not_available_without_key(self):
        """is_available returns False when no api_key."""
        from engines.querit import QueritEngine
        engine = QueritEngine()
        self.assertFalse(engine.is_available({}))

    def test_not_available_with_empty_key(self):
        """is_available returns False when api_key is empty."""
        from engines.querit import QueritEngine
        engine = QueritEngine()
        self.assertFalse(engine.is_available({"api_key": ""}))


if __name__ == "__main__":
    unittest.main()
