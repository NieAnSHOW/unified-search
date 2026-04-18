"""Tests for Exa search engine.

Follows TDD: these tests define the expected behavior of engines/exa.py.
All HTTP calls are mocked via urllib.request.urlopen.
"""

import json
import unittest
from typing import List
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


def _mock_urlopen(response):
    """Return a mock context manager for urlopen."""
    return MagicMock(return_value=response, __enter__=lambda self: response, __exit__=lambda self, *a: None)


# ---------------------------------------------------------------------------
# Sample API responses
# ---------------------------------------------------------------------------

_SAMPLE_RESULTS = [
    {
        "url": "https://example.com/article1",
        "title": "Article One",
        "text": "Full text of article one.",
        "highlights": ["Highlight one", "Highlight two"],
        "score": 0.92,
        "publishedDate": "2025-06-15T10:30:00Z",
    },
    {
        "url": "https://example.com/article2",
        "title": "Article Two",
        "text": "Full text of article two.",
        "highlights": [],
        "score": 0.85,
        "publishedDate": "2025-05-20T08:00:00Z",
    },
    {
        "url": "https://example.com/article3",
        "title": "Article Three",
        "text": "Full text of article three without highlights or date.",
        "highlights": [],
        "score": 0.78,
    },
]


def _sample_response(results=None):
    return {"results": results if results is not None else _SAMPLE_RESULTS}


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------


class TestExaEngineAttributes(unittest.TestCase):
    """Test Exa engine class attributes match the spec."""

    def test_name(self):
        from engines.exa import ExaEngine

        self.assertEqual(ExaEngine.name, "exa")

    def test_display_name(self):
        from engines.exa import ExaEngine

        self.assertEqual(ExaEngine.display_name, "Exa AI")

    def test_priority(self):
        from engines.exa import ExaEngine

        self.assertEqual(ExaEngine.priority, 1)

    def test_requires_key(self):
        from engines.exa import ExaEngine

        self.assertTrue(ExaEngine.requires_key)


class TestExaSearch(unittest.TestCase):
    """Test ExaEngine.search() with mocked HTTP."""

    def _get_engine(self):
        from engines.exa import ExaEngine

        return ExaEngine()

    @patch("engines.exa.urlopen")
    def test_search_returns_search_results(self, mock_urlopen):
        """search() returns a list of SearchResult objects."""
        resp = _MockHTTPResponse(200, _sample_response())
        mock_urlopen.return_value = resp

        engine = self._get_engine()
        config = {"api_key": "test-key"}
        results = engine.search("test query", config=config)

        self.assertIsInstance(results, list)
        self.assertEqual(len(results), 3)
        for r in results:
            self.assertIsInstance(r, SearchResult)

    @patch("engines.exa.urlopen")
    def test_search_max_results(self, mock_urlopen):
        """search() passes numResults in the request body."""
        resp = _MockHTTPResponse(200, _sample_response())
        mock_urlopen.return_value = resp

        engine = self._get_engine()
        engine.search("test", max_results=5, config={"api_key": "test-key"})

        # Inspect the request that was sent
        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        body = json.loads(request_obj.data)
        self.assertEqual(body["numResults"], 5)

    @patch("engines.exa.urlopen")
    def test_search_passes_query(self, mock_urlopen):
        """search() passes the query string in the request body."""
        resp = _MockHTTPResponse(200, _sample_response())
        mock_urlopen.return_value = resp

        engine = self._get_engine()
        engine.search("python async", config={"api_key": "test-key"})

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        body = json.loads(request_obj.data)
        self.assertEqual(body["query"], "python async")

    @patch("engines.exa.urlopen")
    def test_search_type_is_auto(self, mock_urlopen):
        """search() always sets type to 'auto'."""
        resp = _MockHTTPResponse(200, _sample_response())
        mock_urlopen.return_value = resp

        engine = self._get_engine()
        engine.search("test", config={"api_key": "test-key"})

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        body = json.loads(request_obj.data)
        self.assertEqual(body["type"], "auto")

    @patch("engines.exa.urlopen")
    def test_search_includes_highlights_config(self, mock_urlopen):
        """search() includes contents.highlights.maxCharacters in request."""
        resp = _MockHTTPResponse(200, _sample_response())
        mock_urlopen.return_value = resp

        engine = self._get_engine()
        engine.search("test", config={"api_key": "test-key"})

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        body = json.loads(request_obj.data)
        self.assertIn("contents", body)
        self.assertIn("highlights", body["contents"])
        self.assertEqual(body["contents"]["highlights"]["maxCharacters"], 4000)

    @patch("engines.exa.urlopen")
    def test_search_auth_header(self, mock_urlopen):
        """search() sends x-api-key header with the api_key from config."""
        resp = _MockHTTPResponse(200, _sample_response())
        mock_urlopen.return_value = resp

        engine = self._get_engine()
        engine.search("test", config={"api_key": "my-secret-key"})

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        # Request capitalizes header names; check the value in the headers dict
        found = False
        for key, value in request_obj.headers.items():
            if key.lower() == "x-api-key":
                self.assertEqual(value, "my-secret-key")
                found = True
                break
        self.assertTrue(found, "x-api-key header not found in request")

    @patch("engines.exa.urlopen")
    def test_search_endpoint(self, mock_urlopen):
        """search() POSTs to https://api.exa.ai/search."""
        resp = _MockHTTPResponse(200, _sample_response())
        mock_urlopen.return_value = resp

        engine = self._get_engine()
        engine.search("test", config={"api_key": "test-key"})

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        self.assertEqual(request_obj.full_url, "https://api.exa.ai/search")
        self.assertEqual(request_obj.method, "POST")

    @patch("engines.exa.urlopen")
    def test_search_no_api_key_raises(self, mock_urlopen):
        """search() raises ValueError when no api_key is provided in config."""
        engine = self._get_engine()
        with self.assertRaises(ValueError) as ctx:
            engine.search("test", config={})
        self.assertIn("api_key", str(ctx.exception).lower())

    @patch("engines.exa.urlopen")
    def test_search_empty_api_key_raises(self, mock_urlopen):
        """search() raises ValueError when api_key is empty string."""
        engine = self._get_engine()
        with self.assertRaises(ValueError):
            engine.search("test", config={"api_key": ""})

    @patch("engines.exa.urlopen")
    def test_search_no_config_raises(self, mock_urlopen):
        """search() raises ValueError when config is None."""
        engine = self._get_engine()
        with self.assertRaises(ValueError):
            engine.search("test")

    @patch("engines.exa.urlopen")
    def test_search_api_error_raises(self, mock_urlopen):
        """search() propagates API errors (non-200 responses)."""
        from urllib.error import HTTPError

        mock_urlopen.side_effect = HTTPError(
            url="https://api.exa.ai/search",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=None,
        )

        engine = self._get_engine()
        with self.assertRaises(HTTPError):
            engine.search("test", config={"api_key": "bad-key"})


class TestExaNormalize(unittest.TestCase):
    """Test ExaEngine._normalize() field mapping."""

    def _get_engine(self):
        from engines.exa import ExaEngine

        return ExaEngine()

    def test_normalize_maps_title(self):
        """_normalize correctly maps the title field."""
        engine = self._get_engine()
        raw = _SAMPLE_RESULTS
        results = engine._normalize(raw)
        self.assertEqual(results[0].title, "Article One")
        self.assertEqual(results[1].title, "Article Two")
        self.assertEqual(results[2].title, "Article Three")

    def test_normalize_maps_url(self):
        """_normalize correctly maps the url field."""
        engine = self._get_engine()
        results = engine._normalize(_SAMPLE_RESULTS)
        self.assertEqual(results[0].url, "https://example.com/article1")
        self.assertEqual(results[1].url, "https://example.com/article2")

    def test_normalize_snippet_from_highlights(self):
        """_normalize uses highlights joined by newline when available."""
        engine = self._get_engine()
        results = engine._normalize(_SAMPLE_RESULTS)
        # Article 1 has highlights
        self.assertEqual(results[0].snippet, "Highlight one\nHighlight two")

    def test_normalize_snippet_falls_back_to_text(self):
        """_normalize falls back to text (first 400 chars) when highlights list is empty."""
        engine = self._get_engine()
        results = engine._normalize(_SAMPLE_RESULTS)
        # Article 2 has empty highlights, text is short so full text returned
        self.assertEqual(results[1].snippet, "Full text of article two.")

    def test_normalize_snippet_truncates_long_text(self):
        """_normalize truncates text to 400 characters when used as fallback."""
        engine = self._get_engine()
        long_text = "A" * 600
        raw = [
            {
                "url": "https://example.com/long",
                "title": "Long Text",
                "text": long_text,
                "highlights": [],
                "score": 0.5,
            }
        ]
        results = engine._normalize(raw)
        self.assertEqual(len(results[0].snippet), 400)
        self.assertEqual(results[0].snippet, "A" * 400)

    def test_normalize_snippet_falls_back_to_text_no_highlights_key(self):
        """_normalize falls back to text when highlights key is absent."""
        engine = self._get_engine()
        raw = [
            {
                "url": "https://example.com/no-hl",
                "title": "No Highlights Key",
                "text": "Fallback text.",
                "score": 0.5,
            }
        ]
        results = engine._normalize(raw)
        self.assertEqual(results[0].snippet, "Fallback text.")

    def test_normalize_snippet_empty_when_no_text_no_highlights(self):
        """_normalize returns empty string when neither text nor highlights exist."""
        engine = self._get_engine()
        raw = [
            {
                "url": "https://example.com/empty",
                "title": "Empty",
                "score": 0.3,
            }
        ]
        results = engine._normalize(raw)
        self.assertEqual(results[0].snippet, "")

    def test_normalize_published_date(self):
        """_normalize extracts publishedDate when present."""
        engine = self._get_engine()
        results = engine._normalize(_SAMPLE_RESULTS)
        self.assertEqual(results[0].published_date, "2025-06-15T10:30:00Z")
        self.assertEqual(results[1].published_date, "2025-05-20T08:00:00Z")

    def test_normalize_published_date_none_when_missing(self):
        """_normalize sets published_date to None when not in response."""
        engine = self._get_engine()
        results = engine._normalize(_SAMPLE_RESULTS)
        # Article 3 has no publishedDate
        self.assertIsNone(results[2].published_date)

    def test_normalize_score_with_native_score(self):
        """_normalize uses the native score from the API response."""
        engine = self._get_engine()
        results = engine._normalize(_SAMPLE_RESULTS)
        self.assertAlmostEqual(results[0].score, 0.92)
        self.assertAlmostEqual(results[1].score, 0.85)
        self.assertAlmostEqual(results[2].score, 0.78)

    def test_normalize_score_rank_decay_without_native_score(self):
        """_normalize uses rank decay 1.0/(index+1) when no native score."""
        engine = self._get_engine()
        raw = [
            {"url": "https://example.com/a", "title": "A", "text": "text"},
            {"url": "https://example.com/b", "title": "B", "text": "text"},
            {"url": "https://example.com/c", "title": "C", "text": "text"},
        ]
        results = engine._normalize(raw)
        self.assertAlmostEqual(results[0].score, 1.0 / 1)
        self.assertAlmostEqual(results[1].score, 1.0 / 2)
        self.assertAlmostEqual(results[2].score, 1.0 / 3)

    def test_normalize_score_zero_is_falsy_still_uses_native(self):
        """_normalize uses native score even when it is exactly 0.0."""
        engine = self._get_engine()
        raw = [
            {"url": "https://example.com/zero", "title": "Zero", "text": "text", "score": 0.0},
        ]
        results = engine._normalize(raw)
        self.assertEqual(results[0].score, 0.0)

    def test_normalize_source_engine(self):
        """_normalize sets source_engine to ['exa'] for all results."""
        engine = self._get_engine()
        results = engine._normalize(_SAMPLE_RESULTS)
        for r in results:
            self.assertEqual(r.source_engine, ["exa"])

    def test_normalize_empty_results(self):
        """_normalize returns empty list for empty input."""
        engine = self._get_engine()
        results = engine._normalize([])
        self.assertEqual(results, [])


class TestExaFreshness(unittest.TestCase):
    """Test freshness parameter mapping to startPublishedDate."""

    def _get_engine(self):
        from engines.exa import ExaEngine

        return ExaEngine()

    @patch("engines.exa.urlopen")
    def test_freshness_pd_sets_today(self, mock_urlopen):
        """freshness='pd' sets startPublishedDate to today."""
        resp = _MockHTTPResponse(200, _sample_response())
        mock_urlopen.return_value = resp

        engine = self._get_engine()
        engine.search("test", freshness="pd", config={"api_key": "test-key"})

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        body = json.loads(request_obj.data)
        self.assertIn("startPublishedDate", body)

        from datetime import datetime, timezone

        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self.assertEqual(body["startPublishedDate"], today_str)

    @patch("engines.exa.urlopen")
    def test_freshness_pw_sets_monday(self, mock_urlopen):
        """freshness='pw' sets startPublishedDate to start of current week (Monday)."""
        resp = _MockHTTPResponse(200, _sample_response())
        mock_urlopen.return_value = resp

        engine = self._get_engine()
        engine.search("test", freshness="pw", config={"api_key": "test-key"})

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        body = json.loads(request_obj.data)
        self.assertIn("startPublishedDate", body)

        from datetime import datetime, timedelta, timezone

        today = datetime.now(timezone.utc)
        monday = today - timedelta(days=today.weekday())
        expected = monday.strftime("%Y-%m-%d")
        self.assertEqual(body["startPublishedDate"], expected)

    @patch("engines.exa.urlopen")
    def test_freshness_pm_sets_first_of_month(self, mock_urlopen):
        """freshness='pm' sets startPublishedDate to first day of current month."""
        resp = _MockHTTPResponse(200, _sample_response())
        mock_urlopen.return_value = resp

        engine = self._get_engine()
        engine.search("test", freshness="pm", config={"api_key": "test-key"})

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        body = json.loads(request_obj.data)
        self.assertIn("startPublishedDate", body)

        from datetime import datetime, timezone

        today = datetime.now(timezone.utc)
        first_of_month = today.replace(day=1).strftime("%Y-%m-%d")
        self.assertEqual(body["startPublishedDate"], first_of_month)

    @patch("engines.exa.urlopen")
    def test_no_freshness_no_date_filter(self, mock_urlopen):
        """When freshness is None, no startPublishedDate is sent."""
        resp = _MockHTTPResponse(200, _sample_response())
        mock_urlopen.return_value = resp

        engine = self._get_engine()
        engine.search("test", freshness=None, config={"api_key": "test-key"})

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        body = json.loads(request_obj.data)
        self.assertNotIn("startPublishedDate", body)

    @patch("engines.exa.urlopen")
    def test_unknown_freshness_ignored(self, mock_urlopen):
        """An unrecognized freshness value does not add startPublishedDate."""
        resp = _MockHTTPResponse(200, _sample_response())
        mock_urlopen.return_value = resp

        engine = self._get_engine()
        engine.search("test", freshness="py", config={"api_key": "test-key"})

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        body = json.loads(request_obj.data)
        self.assertNotIn("startPublishedDate", body)


class TestExaEmptyResults(unittest.TestCase):
    """Test behavior when API returns no results."""

    @patch("engines.exa.urlopen")
    def test_empty_results_returns_empty_list(self, mock_urlopen):
        """search() returns an empty list when API returns no results."""
        resp = _MockHTTPResponse(200, {"results": []})
        mock_urlopen.return_value = resp

        from engines.exa import ExaEngine

        engine = ExaEngine()
        results = engine.search("nonexistent query", config={"api_key": "test-key"})

        self.assertEqual(results, [])
        self.assertIsInstance(results, list)


class TestExaIsAvailable(unittest.TestCase):
    """Test is_available inherits correctly from BaseEngine."""

    def test_available_with_key(self):
        from engines.exa import ExaEngine

        engine = ExaEngine()
        self.assertTrue(engine.is_available({"api_key": "valid-key"}))

    def test_not_available_without_key(self):
        from engines.exa import ExaEngine

        engine = ExaEngine()
        self.assertFalse(engine.is_available({}))

    def test_not_available_with_empty_key(self):
        from engines.exa import ExaEngine

        engine = ExaEngine()
        self.assertFalse(engine.is_available({"api_key": ""}))


if __name__ == "__main__":
    unittest.main()
