"""Tests for Brave Search engine.

Follows TDD: these tests define the expected behavior of engines/brave.py.
All HTTP calls are mocked via urllib.request.urlopen.
"""

import json
import unittest
from unittest.mock import MagicMock, patch

from engines.base import SearchResult


class _MockHTTPResponse:
    """Simulates an HTTPResponse returned by urlopen."""

    def __init__(self, status_code: int, body: dict):
        self.status_code = status_code
        self._body = json.dumps(body).encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


# ---------------------------------------------------------------------------
# Sample API responses
# ---------------------------------------------------------------------------

_SAMPLE_WEB_RESULTS = [
    {
        "title": "Brave Search Result One",
        "url": "https://example.com/brave-article1",
        "description": "Description of the first result.",
        "extra_snippets": ["Extra snippet one", "Extra snippet two"],
    },
    {
        "title": "Brave Search Result Two",
        "url": "https://example.com/brave-article2",
        "description": "Description of the second result.",
        "extra_snippets": [],
    },
    {
        "title": "Brave Search Result Three",
        "url": "https://example.com/brave-article3",
        "description": "Description of the third result without extra snippets.",
    },
]


def _sample_response(results=None):
    return {"web": {"results": results if results is not None else _SAMPLE_WEB_RESULTS}}


# ---------------------------------------------------------------------------
# Test class: class attributes
# ---------------------------------------------------------------------------


class TestBraveEngineAttributes(unittest.TestCase):
    """Test Brave engine class attributes match the spec."""

    def test_name(self):
        from engines.brave import BraveEngine

        self.assertEqual(BraveEngine.name, "brave")

    def test_display_name(self):
        from engines.brave import BraveEngine

        self.assertEqual(BraveEngine.display_name, "Brave Search")

    def test_priority(self):
        from engines.brave import BraveEngine

        self.assertEqual(BraveEngine.priority, 5)

    def test_requires_key(self):
        from engines.brave import BraveEngine

        self.assertTrue(BraveEngine.requires_key)


# ---------------------------------------------------------------------------
# Test class: search()
# ---------------------------------------------------------------------------


class TestBraveSearch(unittest.TestCase):
    """Test BraveEngine.search() with mocked HTTP."""

    def _get_engine(self):
        from engines.brave import BraveEngine

        return BraveEngine()

    @patch("engines.brave.urlopen")
    def test_search_returns_search_results(self, mock_urlopen):
        """search() returns a list of SearchResult objects."""
        resp = _MockHTTPResponse(200, _sample_response())
        mock_urlopen.return_value = resp

        engine = self._get_engine()
        results = engine.search("test query", config={"api_key": "test-key"})

        self.assertIsInstance(results, list)
        self.assertEqual(len(results), 3)
        for r in results:
            self.assertIsInstance(r, SearchResult)

    @patch("engines.brave.urlopen")
    def test_search_passes_query(self, mock_urlopen):
        """search() passes the query string as a URL parameter."""
        resp = _MockHTTPResponse(200, _sample_response())
        mock_urlopen.return_value = resp

        engine = self._get_engine()
        engine.search("python async await", config={"api_key": "test-key"})

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        # The query should be URL-encoded in the request URL
        self.assertIn("q=python+async+await", request_obj.full_url)

    @patch("engines.brave.urlopen")
    def test_search_passes_count(self, mock_urlopen):
        """search() passes count as a URL parameter."""
        resp = _MockHTTPResponse(200, _sample_response())
        mock_urlopen.return_value = resp

        engine = self._get_engine()
        engine.search("test", max_results=5, config={"api_key": "test-key"})

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        self.assertIn("count=5", request_obj.full_url)

    @patch("engines.brave.urlopen")
    def test_search_auth_header(self, mock_urlopen):
        """search() sends X-Subscription-Token header with the api_key."""
        resp = _MockHTTPResponse(200, _sample_response())
        mock_urlopen.return_value = resp

        engine = self._get_engine()
        engine.search("test", config={"api_key": "my-brave-key"})

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        # urllib.request.Request capitalizes header names internally
        self.assertEqual(
            request_obj.get_header("X-subscription-token"), "my-brave-key"
        )

    @patch("engines.brave.urlopen")
    def test_search_endpoint(self, mock_urlopen):
        """search() GETs https://api.search.brave.com/res/v1/web/search."""
        resp = _MockHTTPResponse(200, _sample_response())
        mock_urlopen.return_value = resp

        engine = self._get_engine()
        engine.search("test", config={"api_key": "test-key"})

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        self.assertIn("https://api.search.brave.com/res/v1/web/search", request_obj.full_url)
        self.assertEqual(request_obj.method, "GET")

    @patch("engines.brave.urlopen")
    def test_search_no_api_key_raises(self, mock_urlopen):
        """search() raises ValueError when no api_key is provided in config."""
        engine = self._get_engine()
        with self.assertRaises(ValueError) as ctx:
            engine.search("test", config={})
        self.assertIn("api_key", str(ctx.exception).lower())

    @patch("engines.brave.urlopen")
    def test_search_empty_api_key_raises(self, mock_urlopen):
        """search() raises ValueError when api_key is empty string."""
        engine = self._get_engine()
        with self.assertRaises(ValueError):
            engine.search("test", config={"api_key": ""})

    @patch("engines.brave.urlopen")
    def test_search_no_config_raises(self, mock_urlopen):
        """search() raises ValueError when config is None."""
        engine = self._get_engine()
        with self.assertRaises(ValueError):
            engine.search("test")

    @patch("engines.brave.urlopen")
    def test_search_api_error_raises(self, mock_urlopen):
        """search() propagates API errors (non-200 responses)."""
        from urllib.error import HTTPError

        mock_urlopen.side_effect = HTTPError(
            url="https://api.search.brave.com/res/v1/web/search",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=None,
        )

        engine = self._get_engine()
        with self.assertRaises(HTTPError):
            engine.search("test", config={"api_key": "bad-key"})


# ---------------------------------------------------------------------------
# Test class: _normalize() field mapping
# ---------------------------------------------------------------------------


class TestBraveNormalize(unittest.TestCase):
    """Test BraveEngine._normalize() field mapping."""

    def _get_engine(self):
        from engines.brave import BraveEngine

        return BraveEngine()

    def test_normalize_maps_title(self):
        """_normalize correctly maps the title field."""
        engine = self._get_engine()
        results = engine._normalize(_SAMPLE_WEB_RESULTS)
        self.assertEqual(results[0].title, "Brave Search Result One")
        self.assertEqual(results[1].title, "Brave Search Result Two")
        self.assertEqual(results[2].title, "Brave Search Result Three")

    def test_normalize_maps_url(self):
        """_normalize correctly maps the url field."""
        engine = self._get_engine()
        results = engine._normalize(_SAMPLE_WEB_RESULTS)
        self.assertEqual(results[0].url, "https://example.com/brave-article1")
        self.assertEqual(results[1].url, "https://example.com/brave-article2")

    def test_normalize_maps_description_to_snippet(self):
        """_normalize maps description to snippet when no extra_snippets."""
        engine = self._get_engine()
        # Use a result with no extra_snippets to isolate description mapping
        raw = [
            {
                "title": "Desc Only",
                "url": "https://example.com/desc",
                "description": "Just a description.",
            }
        ]
        results = engine._normalize(raw)
        self.assertEqual(results[0].snippet, "Just a description.")

    def test_normalize_extra_snippets_appended_to_snippet(self):
        """_normalize appends extra_snippets to the description."""
        engine = self._get_engine()
        results = engine._normalize(_SAMPLE_WEB_RESULTS)
        # Result 1 has extra_snippets
        self.assertEqual(
            results[0].snippet,
            "Description of the first result. Extra snippet one Extra snippet two",
        )

    def test_normalize_no_extra_snippets(self):
        """_normalize works when extra_snippets is missing."""
        engine = self._get_engine()
        results = engine._normalize(_SAMPLE_WEB_RESULTS)
        # Result 3 has no extra_snippets key at all
        self.assertEqual(
            results[2].snippet,
            "Description of the third result without extra snippets.",
        )

    def test_normalize_empty_extra_snippets(self):
        """_normalize works when extra_snippets is an empty list."""
        engine = self._get_engine()
        results = engine._normalize(_SAMPLE_WEB_RESULTS)
        # Result 2 has empty extra_snippets
        self.assertEqual(results[1].snippet, "Description of the second result.")

    def test_normalize_score_rank_decay(self):
        """_normalize assigns score as 1.0 / (index + 1)."""
        engine = self._get_engine()
        results = engine._normalize(_SAMPLE_WEB_RESULTS)
        self.assertAlmostEqual(results[0].score, 1.0)
        self.assertAlmostEqual(results[1].score, 1.0 / 2)
        self.assertAlmostEqual(results[2].score, 1.0 / 3)

    def test_normalize_source_engine(self):
        """_normalize sets source_engine to ['brave'] for all results."""
        engine = self._get_engine()
        results = engine._normalize(_SAMPLE_WEB_RESULTS)
        for r in results:
            self.assertEqual(r.source_engine, ["brave"])

    def test_normalize_published_date_none(self):
        """_normalize sets published_date to None (Brave API doesn't provide it at top level)."""
        engine = self._get_engine()
        results = engine._normalize(_SAMPLE_WEB_RESULTS)
        for r in results:
            self.assertIsNone(r.published_date)

    def test_normalize_empty_results(self):
        """_normalize returns empty list for empty input."""
        engine = self._get_engine()
        results = engine._normalize([])
        self.assertEqual(results, [])


# ---------------------------------------------------------------------------
# Test class: freshness parameter
# ---------------------------------------------------------------------------


class TestBraveFreshness(unittest.TestCase):
    """Test freshness parameter mapping to URL query params."""

    def _get_engine(self):
        from engines.brave import BraveEngine

        return BraveEngine()

    @patch("engines.brave.urlopen")
    def test_freshness_pd(self, mock_urlopen):
        """freshness='pd' passes freshness=pd in URL params."""
        resp = _MockHTTPResponse(200, _sample_response())
        mock_urlopen.return_value = resp

        engine = self._get_engine()
        engine.search("test", freshness="pd", config={"api_key": "test-key"})

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        self.assertIn("freshness=pd", request_obj.full_url)

    @patch("engines.brave.urlopen")
    def test_freshness_pw(self, mock_urlopen):
        """freshness='pw' passes freshness=pw in URL params."""
        resp = _MockHTTPResponse(200, _sample_response())
        mock_urlopen.return_value = resp

        engine = self._get_engine()
        engine.search("test", freshness="pw", config={"api_key": "test-key"})

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        self.assertIn("freshness=pw", request_obj.full_url)

    @patch("engines.brave.urlopen")
    def test_freshness_pm(self, mock_urlopen):
        """freshness='pm' passes freshness=pm in URL params."""
        resp = _MockHTTPResponse(200, _sample_response())
        mock_urlopen.return_value = resp

        engine = self._get_engine()
        engine.search("test", freshness="pm", config={"api_key": "test-key"})

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        self.assertIn("freshness=pm", request_obj.full_url)

    @patch("engines.brave.urlopen")
    def test_freshness_py(self, mock_urlopen):
        """freshness='py' passes freshness=py in URL params."""
        resp = _MockHTTPResponse(200, _sample_response())
        mock_urlopen.return_value = resp

        engine = self._get_engine()
        engine.search("test", freshness="py", config={"api_key": "test-key"})

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        self.assertIn("freshness=py", request_obj.full_url)

    @patch("engines.brave.urlopen")
    def test_no_freshness(self, mock_urlopen):
        """When freshness is None, no freshness param is in the URL."""
        resp = _MockHTTPResponse(200, _sample_response())
        mock_urlopen.return_value = resp

        engine = self._get_engine()
        engine.search("test", freshness=None, config={"api_key": "test-key"})

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        self.assertNotIn("freshness=", request_obj.full_url)


# ---------------------------------------------------------------------------
# Test class: empty results
# ---------------------------------------------------------------------------


class TestBraveEmptyResults(unittest.TestCase):
    """Test behavior when API returns no results."""

    @patch("engines.brave.urlopen")
    def test_empty_results_returns_empty_list(self, mock_urlopen):
        """search() returns an empty list when API returns no results."""
        resp = _MockHTTPResponse(200, {"web": {"results": []}})
        mock_urlopen.return_value = resp

        from engines.brave import BraveEngine

        engine = BraveEngine()
        results = engine.search("nonexistent query", config={"api_key": "test-key"})

        self.assertEqual(results, [])
        self.assertIsInstance(results, list)


# ---------------------------------------------------------------------------
# Test class: is_available
# ---------------------------------------------------------------------------


class TestBraveIsAvailable(unittest.TestCase):
    """Test is_available inherits correctly from BaseEngine."""

    def test_available_with_key(self):
        from engines.brave import BraveEngine

        engine = BraveEngine()
        self.assertTrue(engine.is_available({"api_key": "valid-key"}))

    def test_not_available_without_key(self):
        from engines.brave import BraveEngine

        engine = BraveEngine()
        self.assertFalse(engine.is_available({}))

    def test_not_available_with_empty_key(self):
        from engines.brave import BraveEngine

        engine = BraveEngine()
        self.assertFalse(engine.is_available({"api_key": ""}))


if __name__ == "__main__":
    unittest.main()
