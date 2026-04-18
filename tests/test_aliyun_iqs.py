"""Tests for Aliyun IQS (夸克) search engine.

Follows TDD: these tests define the expected behavior of engines/aliyun_iqs.py.
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

_SAMPLE_RESULTS = [
    {
        "title": "Article One",
        "link": "https://example.com/article1",
        "snippet": "Snippet for article one.",
        "mainText": "Full main text of article one.",
        "publishedTime": "2025-06-15",
        "rerankScore": 0.95,
    },
    {
        "title": "Article Two",
        "link": "https://example.com/article2",
        "snippet": "Snippet for article two.",
        "mainText": "",
        "publishedTime": "2025-05-20",
        "rerankScore": 0.87,
    },
    {
        "title": "Article Three",
        "link": "https://example.com/article3",
        "snippet": "",
        "mainText": "Main text only, no snippet.",
        "publishedTime": "",
        "rerankScore": 0.72,
    },
]

_SAMPLE_RESULTS_NO_SCORE = [
    {
        "title": "No Score Article",
        "link": "https://example.com/no-score",
        "snippet": "Snippet without score.",
        "mainText": "",
    },
    {
        "title": "Another No Score",
        "link": "https://example.com/no-score2",
        "snippet": "Another snippet without score.",
        "mainText": "",
    },
]


def _sample_response(results=None):
    return {"pageItems": results if results is not None else _SAMPLE_RESULTS}


# ---------------------------------------------------------------------------
# Test class: engine attributes
# ---------------------------------------------------------------------------


class TestAliyunIQSEngineAttributes(unittest.TestCase):
    """Test Aliyun IQS engine class attributes match the spec."""

    def test_name(self):
        from engines.aliyun_iqs import AliyunIQSEngine

        self.assertEqual(AliyunIQSEngine.name, "aliyun_iqs")

    def test_display_name(self):
        from engines.aliyun_iqs import AliyunIQSEngine

        self.assertEqual(AliyunIQSEngine.display_name, "Aliyun IQS (夸克)")

    def test_priority(self):
        from engines.aliyun_iqs import AliyunIQSEngine

        self.assertEqual(AliyunIQSEngine.priority, 4)

    def test_requires_key(self):
        from engines.aliyun_iqs import AliyunIQSEngine

        self.assertTrue(AliyunIQSEngine.requires_key)


# ---------------------------------------------------------------------------
# Test class: search()
# ---------------------------------------------------------------------------


class TestAliyunIQSSearch(unittest.TestCase):
    """Test AliyunIQSEngine.search() with mocked HTTP."""

    def _get_engine(self):
        from engines.aliyun_iqs import AliyunIQSEngine

        return AliyunIQSEngine()

    @patch("engines.aliyun_iqs.urlopen")
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

    @patch("engines.aliyun_iqs.urlopen")
    def test_search_max_results(self, mock_urlopen):
        """search() passes count in the request body."""
        resp = _MockHTTPResponse(200, _sample_response())
        mock_urlopen.return_value = resp

        engine = self._get_engine()
        engine.search("test", max_results=5, config={"api_key": "test-key"})

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        body = json.loads(request_obj.data)
        self.assertEqual(body["count"], 5)

    @patch("engines.aliyun_iqs.urlopen")
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

    @patch("engines.aliyun_iqs.urlopen")
    def test_search_engine_type(self, mock_urlopen):
        """search() sets engine to 'LiteAdvanced' by default."""
        resp = _MockHTTPResponse(200, _sample_response())
        mock_urlopen.return_value = resp

        engine = self._get_engine()
        engine.search("test", config={"api_key": "test-key"})

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        body = json.loads(request_obj.data)
        self.assertEqual(body["engine"], "LiteAdvanced")

    @patch("engines.aliyun_iqs.urlopen")
    def test_search_custom_engine_type(self, mock_urlopen):
        """search() uses engine_type from config if provided."""
        resp = _MockHTTPResponse(200, _sample_response())
        mock_urlopen.return_value = resp

        engine = self._get_engine()
        engine.search(
            "test",
            config={"api_key": "test-key", "engine_type": "LiteStandard"},
        )

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        body = json.loads(request_obj.data)
        self.assertEqual(body["engine"], "LiteStandard")

    @patch("engines.aliyun_iqs.urlopen")
    def test_search_auth_header(self, mock_urlopen):
        """search() sends Bearer token in Authorization header."""
        resp = _MockHTTPResponse(200, _sample_response())
        mock_urlopen.return_value = resp

        engine = self._get_engine()
        engine.search("test", config={"api_key": "my-secret-key"})

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        self.assertEqual(
            request_obj.get_header("Authorization"), "Bearer my-secret-key"
        )

    @patch("engines.aliyun_iqs.urlopen")
    def test_search_endpoint(self, mock_urlopen):
        """search() POSTs to the correct endpoint."""
        resp = _MockHTTPResponse(200, _sample_response())
        mock_urlopen.return_value = resp

        engine = self._get_engine()
        engine.search("test", config={"api_key": "test-key"})

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        self.assertEqual(
            request_obj.full_url, "https://cloud-iqs.aliyuncs.com/search/unified"
        )
        self.assertEqual(request_obj.method, "POST")

    @patch("engines.aliyun_iqs.urlopen")
    def test_search_no_api_key_raises(self, mock_urlopen):
        """search() raises ValueError when no api_key is provided."""
        engine = self._get_engine()
        with self.assertRaises(ValueError) as ctx:
            engine.search("test", config={})
        self.assertIn("api_key", str(ctx.exception).lower())

    @patch("engines.aliyun_iqs.urlopen")
    def test_search_empty_api_key_raises(self, mock_urlopen):
        """search() raises ValueError when api_key is empty string."""
        engine = self._get_engine()
        with self.assertRaises(ValueError):
            engine.search("test", config={"api_key": ""})

    @patch("engines.aliyun_iqs.urlopen")
    def test_search_no_config_raises(self, mock_urlopen):
        """search() raises ValueError when config is None."""
        engine = self._get_engine()
        with self.assertRaises(ValueError):
            engine.search("test")

    @patch("engines.aliyun_iqs.urlopen")
    def test_search_api_error_raises(self, mock_urlopen):
        """search() propagates API errors (non-200 responses)."""
        from urllib.error import HTTPError

        mock_urlopen.side_effect = HTTPError(
            url="https://cloud-iqs.aliyuncs.com/search/unified",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=None,
        )

        engine = self._get_engine()
        with self.assertRaises(HTTPError):
            engine.search("test", config={"api_key": "bad-key"})


# ---------------------------------------------------------------------------
# Test class: _normalize()
# ---------------------------------------------------------------------------


class TestAliyunIQSNormalize(unittest.TestCase):
    """Test AliyunIQSEngine._normalize() field mapping."""

    def _get_engine(self):
        from engines.aliyun_iqs import AliyunIQSEngine

        return AliyunIQSEngine()

    def test_normalize_maps_title(self):
        """_normalize correctly maps the title field."""
        engine = self._get_engine()
        results = engine._normalize(_SAMPLE_RESULTS)
        self.assertEqual(results[0].title, "Article One")
        self.assertEqual(results[1].title, "Article Two")
        self.assertEqual(results[2].title, "Article Three")

    def test_normalize_maps_link_to_url(self):
        """_normalize maps 'link' to 'url'."""
        engine = self._get_engine()
        results = engine._normalize(_SAMPLE_RESULTS)
        self.assertEqual(results[0].url, "https://example.com/article1")
        self.assertEqual(results[1].url, "https://example.com/article2")

    def test_normalize_snippet_from_snippet_field(self):
        """_normalize uses 'snippet' field when available and non-empty."""
        engine = self._get_engine()
        results = engine._normalize(_SAMPLE_RESULTS)
        self.assertEqual(results[0].snippet, "Snippet for article one.")
        self.assertEqual(results[1].snippet, "Snippet for article two.")

    def test_normalize_snippet_falls_back_to_mainText(self):
        """_normalize falls back to 'mainText' when snippet is empty."""
        engine = self._get_engine()
        results = engine._normalize(_SAMPLE_RESULTS)
        # Article 3 has empty snippet, should use mainText
        self.assertEqual(results[2].snippet, "Main text only, no snippet.")

    def test_normalize_snippet_empty_when_both_missing(self):
        """_normalize returns empty string when both snippet and mainText are missing."""
        engine = self._get_engine()
        raw = [
            {
                "title": "Empty",
                "link": "https://example.com/empty",
            }
        ]
        results = engine._normalize(raw)
        self.assertEqual(results[0].snippet, "")

    def test_normalize_published_time(self):
        """_normalize maps 'publishedTime' to 'published_date'."""
        engine = self._get_engine()
        results = engine._normalize(_SAMPLE_RESULTS)
        self.assertEqual(results[0].published_date, "2025-06-15")
        self.assertEqual(results[1].published_date, "2025-05-20")

    def test_normalize_published_date_none_when_empty(self):
        """_normalize sets published_date to None when publishedTime is empty."""
        engine = self._get_engine()
        results = engine._normalize(_SAMPLE_RESULTS)
        self.assertIsNone(results[2].published_date)

    def test_normalize_published_date_none_when_missing(self):
        """_normalize sets published_date to None when publishedTime is absent."""
        engine = self._get_engine()
        raw = [
            {
                "title": "No Date",
                "link": "https://example.com/no-date",
                "snippet": "No date here.",
            }
        ]
        results = engine._normalize(raw)
        self.assertIsNone(results[0].published_date)

    def test_normalize_rerankScore_to_score(self):
        """_normalize maps 'rerankScore' to 'score'."""
        engine = self._get_engine()
        results = engine._normalize(_SAMPLE_RESULTS)
        self.assertAlmostEqual(results[0].score, 0.95)
        self.assertAlmostEqual(results[1].score, 0.87)
        self.assertAlmostEqual(results[2].score, 0.72)

    def test_normalize_score_rank_decay_without_rerankScore(self):
        """_normalize uses rank-based decay when rerankScore is absent.

        Decay formula: score = 1.0 / (rank + 1) where rank starts at 0.
        """
        engine = self._get_engine()
        results = engine._normalize(_SAMPLE_RESULTS_NO_SCORE)
        self.assertAlmostEqual(results[0].score, 1.0 / (0 + 1))
        self.assertAlmostEqual(results[1].score, 1.0 / (1 + 1))

    def test_normalize_score_default_zero_when_no_rerankScore_single(self):
        """_normalize for a single item without rerankScore uses rank 0 decay."""
        engine = self._get_engine()
        raw = [
            {
                "title": "Single",
                "link": "https://example.com/single",
                "snippet": "Only result.",
            }
        ]
        results = engine._normalize(raw)
        self.assertAlmostEqual(results[0].score, 1.0)

    def test_normalize_source_engine(self):
        """_normalize sets source_engine to ['aliyun_iqs'] for all results."""
        engine = self._get_engine()
        results = engine._normalize(_SAMPLE_RESULTS)
        for r in results:
            self.assertEqual(r.source_engine, ["aliyun_iqs"])

    def test_normalize_empty_results(self):
        """_normalize returns empty list for empty input."""
        engine = self._get_engine()
        results = engine._normalize([])
        self.assertEqual(results, [])


# ---------------------------------------------------------------------------
# Test class: freshness
# ---------------------------------------------------------------------------


class TestAliyunIQSFreshness(unittest.TestCase):
    """Test freshness parameter mapping to startDate/endDate."""

    def _get_engine(self):
        from engines.aliyun_iqs import AliyunIQSEngine

        return AliyunIQSEngine()

    @patch("engines.aliyun_iqs.urlopen")
    def test_freshness_pd_sets_startDate_today(self, mock_urlopen):
        """freshness='pd' sets startDate to today."""
        resp = _MockHTTPResponse(200, _sample_response())
        mock_urlopen.return_value = resp

        engine = self._get_engine()
        engine.search("test", freshness="pd", config={"api_key": "test-key"})

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        body = json.loads(request_obj.data)
        self.assertIn("startDate", body)

        from datetime import datetime, timezone

        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self.assertEqual(body["startDate"], today_str)

    @patch("engines.aliyun_iqs.urlopen")
    def test_freshness_pw_sets_startDate_monday(self, mock_urlopen):
        """freshness='pw' sets startDate to start of current week (Monday)."""
        resp = _MockHTTPResponse(200, _sample_response())
        mock_urlopen.return_value = resp

        engine = self._get_engine()
        engine.search("test", freshness="pw", config={"api_key": "test-key"})

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        body = json.loads(request_obj.data)
        self.assertIn("startDate", body)

        from datetime import datetime, timedelta, timezone

        today = datetime.now(timezone.utc)
        monday = today - timedelta(days=today.weekday())
        expected = monday.strftime("%Y-%m-%d")
        self.assertEqual(body["startDate"], expected)

    @patch("engines.aliyun_iqs.urlopen")
    def test_freshness_pm_sets_startDate_first_of_month(self, mock_urlopen):
        """freshness='pm' sets startDate to first day of current month."""
        resp = _MockHTTPResponse(200, _sample_response())
        mock_urlopen.return_value = resp

        engine = self._get_engine()
        engine.search("test", freshness="pm", config={"api_key": "test-key"})

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        body = json.loads(request_obj.data)
        self.assertIn("startDate", body)

        from datetime import datetime, timezone

        today = datetime.now(timezone.utc)
        first_of_month = today.replace(day=1).strftime("%Y-%m-%d")
        self.assertEqual(body["startDate"], first_of_month)

    @patch("engines.aliyun_iqs.urlopen")
    def test_no_freshness_no_date_filter(self, mock_urlopen):
        """When freshness is None, no startDate/endDate is sent."""
        resp = _MockHTTPResponse(200, _sample_response())
        mock_urlopen.return_value = resp

        engine = self._get_engine()
        engine.search("test", freshness=None, config={"api_key": "test-key"})

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        body = json.loads(request_obj.data)
        self.assertNotIn("startDate", body)
        self.assertNotIn("endDate", body)

    @patch("engines.aliyun_iqs.urlopen")
    def test_unknown_freshness_ignored(self, mock_urlopen):
        """An unrecognized freshness value does not add startDate/endDate."""
        resp = _MockHTTPResponse(200, _sample_response())
        mock_urlopen.return_value = resp

        engine = self._get_engine()
        engine.search("test", freshness="py", config={"api_key": "test-key"})

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        body = json.loads(request_obj.data)
        self.assertNotIn("startDate", body)
        self.assertNotIn("endDate", body)


# ---------------------------------------------------------------------------
# Test class: empty results
# ---------------------------------------------------------------------------


class TestAliyunIQSEmptyResults(unittest.TestCase):
    """Test behavior when API returns no results."""

    @patch("engines.aliyun_iqs.urlopen")
    def test_empty_results_returns_empty_list(self, mock_urlopen):
        """search() returns an empty list when API returns no results."""
        resp = _MockHTTPResponse(200, {"pageItems": []})
        mock_urlopen.return_value = resp

        from engines.aliyun_iqs import AliyunIQSEngine

        engine = AliyunIQSEngine()
        results = engine.search(
            "nonexistent query", config={"api_key": "test-key"}
        )

        self.assertEqual(results, [])
        self.assertIsInstance(results, list)


# ---------------------------------------------------------------------------
# Test class: is_available
# ---------------------------------------------------------------------------


class TestAliyunIQSIsAvailable(unittest.TestCase):
    """Test is_available inherits correctly from BaseEngine."""

    def test_available_with_key(self):
        from engines.aliyun_iqs import AliyunIQSEngine

        engine = AliyunIQSEngine()
        self.assertTrue(engine.is_available({"api_key": "valid-key"}))

    def test_not_available_without_key(self):
        from engines.aliyun_iqs import AliyunIQSEngine

        engine = AliyunIQSEngine()
        self.assertFalse(engine.is_available({}))

    def test_not_available_with_empty_key(self):
        from engines.aliyun_iqs import AliyunIQSEngine

        engine = AliyunIQSEngine()
        self.assertFalse(engine.is_available({"api_key": ""}))


if __name__ == "__main__":
    unittest.main()
