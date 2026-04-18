"""Tests for Metaso (秘塔) search engine.

Follows TDD: these tests define the expected behavior of engines/metaso.py.
All HTTP calls are mocked via urllib.request.urlopen.
"""

import json
import unittest
from unittest.mock import patch

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
# Sample API responses — Format A (nested data.results)
# ---------------------------------------------------------------------------

_SAMPLE_FORMAT_A_RESULTS = [
    {
        "title": "秘塔搜索结果一",
        "url": "https://example.com/metaso-article1",
        "content": "这是第一条结果的摘要内容。",
        "date": "2026-04-08",
    },
    {
        "title": "秘塔搜索结果二",
        "url": "https://example.com/metaso-article2",
        "content": "这是第二条结果的摘要内容。",
        "date": "2026-04-07",
    },
    {
        "title": "秘塔搜索结果三",
        "url": "https://example.com/metaso-article3",
        "content": "第三条结果没有日期。",
    },
]


def _sample_response_format_a(results=None):
    return {
        "data": {
            "results": results if results is not None else _SAMPLE_FORMAT_A_RESULTS
        }
    }


# ---------------------------------------------------------------------------
# Sample API responses — Format B (flat items)
# ---------------------------------------------------------------------------

_SAMPLE_FORMAT_B_RESULTS = [
    {
        "title": "Format B 结果一",
        "url": "https://example.com/formatb-article1",
        "snippet": "格式B的第一条摘要。",
        "publish_time": "2026-04-06",
    },
    {
        "title": "Format B 结果二",
        "url": "https://example.com/formatb-article2",
        "snippet": "格式B的第二条摘要。",
        "publish_time": "2026-04-05",
    },
]


def _sample_response_format_b(results=None):
    return {"items": results if results is not None else _SAMPLE_FORMAT_B_RESULTS}


# ---------------------------------------------------------------------------
# Test class: class attributes
# ---------------------------------------------------------------------------


class TestMetasoEngineAttributes(unittest.TestCase):
    """Test Metaso engine class attributes match the spec."""

    def test_name(self):
        from engines.metaso import MetasoEngine

        self.assertEqual(MetasoEngine.name, "metaso")

    def test_display_name(self):
        from engines.metaso import MetasoEngine

        self.assertEqual(MetasoEngine.display_name, "Metaso (秘塔)")

    def test_priority(self):
        from engines.metaso import MetasoEngine

        self.assertEqual(MetasoEngine.priority, 3)

    def test_requires_key(self):
        from engines.metaso import MetasoEngine

        self.assertTrue(MetasoEngine.requires_key)


# ---------------------------------------------------------------------------
# Test class: search()
# ---------------------------------------------------------------------------


class TestMetasoSearch(unittest.TestCase):
    """Test MetasoEngine.search() with mocked HTTP."""

    def _get_engine(self):
        from engines.metaso import MetasoEngine

        return MetasoEngine()

    @patch("engines.metaso.urlopen")
    def test_search_returns_search_results(self, mock_urlopen):
        """search() returns a list of SearchResult objects."""
        resp = _MockHTTPResponse(200, _sample_response_format_a())
        mock_urlopen.return_value = resp

        engine = self._get_engine()
        results = engine.search("测试查询", config={"api_key": "mk-test-key"})

        self.assertIsInstance(results, list)
        self.assertEqual(len(results), 3)
        for r in results:
            self.assertIsInstance(r, SearchResult)

    @patch("engines.metaso.urlopen")
    def test_search_passes_query_in_body(self, mock_urlopen):
        """search() includes the query string in the POST body."""
        resp = _MockHTTPResponse(200, _sample_response_format_a())
        mock_urlopen.return_value = resp

        engine = self._get_engine()
        engine.search("Python 异步编程", config={"api_key": "mk-test-key"})

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        body = json.loads(request_obj.data.decode("utf-8"))
        self.assertEqual(body["query"], "Python 异步编程")

    @patch("engines.metaso.urlopen")
    def test_search_passes_scope_in_body(self, mock_urlopen):
        """search() includes scope='webpage' in the POST body."""
        resp = _MockHTTPResponse(200, _sample_response_format_a())
        mock_urlopen.return_value = resp

        engine = self._get_engine()
        engine.search("test", config={"api_key": "mk-test-key"})

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        body = json.loads(request_obj.data.decode("utf-8"))
        self.assertEqual(body["scope"], "webpage")

    @patch("engines.metaso.urlopen")
    def test_search_endpoint_is_post(self, mock_urlopen):
        """search() POSTs to https://metaso.cn/api/v1/search."""
        resp = _MockHTTPResponse(200, _sample_response_format_a())
        mock_urlopen.return_value = resp

        engine = self._get_engine()
        engine.search("test", config={"api_key": "mk-test-key"})

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        self.assertEqual(request_obj.full_url, "https://metaso.cn/api/v1/search")
        self.assertEqual(request_obj.method, "POST")

    @patch("engines.metaso.urlopen")
    def test_search_auth_header(self, mock_urlopen):
        """search() sends Authorization: Bearer header with the api_key."""
        resp = _MockHTTPResponse(200, _sample_response_format_a())
        mock_urlopen.return_value = resp

        engine = self._get_engine()
        engine.search("test", config={"api_key": "mk-secret123"})

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        self.assertEqual(
            request_obj.get_header("Authorization"), "Bearer mk-secret123"
        )

    @patch("engines.metaso.urlopen")
    def test_search_no_api_key_raises(self, mock_urlopen):
        """search() raises ValueError when no api_key is provided in config."""
        engine = self._get_engine()
        with self.assertRaises(ValueError) as ctx:
            engine.search("test", config={})
        self.assertIn("api_key", str(ctx.exception).lower())

    @patch("engines.metaso.urlopen")
    def test_search_empty_api_key_raises(self, mock_urlopen):
        """search() raises ValueError when api_key is empty string."""
        engine = self._get_engine()
        with self.assertRaises(ValueError):
            engine.search("test", config={"api_key": ""})

    @patch("engines.metaso.urlopen")
    def test_search_no_config_raises(self, mock_urlopen):
        """search() raises ValueError when config is None."""
        engine = self._get_engine()
        with self.assertRaises(ValueError):
            engine.search("test")

    @patch("engines.metaso.urlopen")
    def test_search_api_error_raises(self, mock_urlopen):
        """search() propagates API errors (non-200 responses)."""
        from urllib.error import HTTPError

        mock_urlopen.side_effect = HTTPError(
            url="https://metaso.cn/api/v1/search",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=None,
        )

        engine = self._get_engine()
        with self.assertRaises(HTTPError):
            engine.search("test", config={"api_key": "bad-key"})


# ---------------------------------------------------------------------------
# Test class: _normalize() field mapping — Format A
# ---------------------------------------------------------------------------


class TestMetasoNormalizeFormatA(unittest.TestCase):
    """Test MetasoEngine._normalize() with Format A response."""

    def _get_engine(self):
        from engines.metaso import MetasoEngine

        return MetasoEngine()

    def test_normalize_format_a_maps_title(self):
        """_normalize correctly maps title from Format A."""
        engine = self._get_engine()
        raw = _SAMPLE_FORMAT_A_RESULTS
        results = engine._normalize(raw)
        self.assertEqual(results[0].title, "秘塔搜索结果一")
        self.assertEqual(results[1].title, "秘塔搜索结果二")

    def test_normalize_format_a_maps_url(self):
        """_normalize correctly maps url from Format A."""
        engine = self._get_engine()
        results = engine._normalize(_SAMPLE_FORMAT_A_RESULTS)
        self.assertEqual(results[0].url, "https://example.com/metaso-article1")

    def test_normalize_format_a_maps_content_to_snippet(self):
        """_normalize maps 'content' to snippet in Format A."""
        engine = self._get_engine()
        results = engine._normalize(_SAMPLE_FORMAT_A_RESULTS)
        self.assertEqual(results[0].snippet, "这是第一条结果的摘要内容。")

    def test_normalize_format_a_maps_date(self):
        """_normalize maps 'date' to published_date in Format A."""
        engine = self._get_engine()
        results = engine._normalize(_SAMPLE_FORMAT_A_RESULTS)
        self.assertEqual(results[0].published_date, "2026-04-08")
        self.assertEqual(results[1].published_date, "2026-04-07")

    def test_normalize_format_a_missing_date_is_none(self):
        """_normalize sets published_date to None when date is missing in Format A."""
        engine = self._get_engine()
        results = engine._normalize(_SAMPLE_FORMAT_A_RESULTS)
        self.assertIsNone(results[2].published_date)


# ---------------------------------------------------------------------------
# Test class: _normalize() field mapping — Format B
# ---------------------------------------------------------------------------


class TestMetasoNormalizeFormatB(unittest.TestCase):
    """Test MetasoEngine._normalize() with Format B response."""

    def _get_engine(self):
        from engines.metaso import MetasoEngine

        return MetasoEngine()

    def test_normalize_format_b_maps_title(self):
        """_normalize correctly maps title from Format B."""
        engine = self._get_engine()
        raw = _SAMPLE_FORMAT_B_RESULTS
        results = engine._normalize(raw)
        self.assertEqual(results[0].title, "Format B 结果一")

    def test_normalize_format_b_maps_url(self):
        """_normalize correctly maps url from Format B."""
        engine = self._get_engine()
        results = engine._normalize(_SAMPLE_FORMAT_B_RESULTS)
        self.assertEqual(results[0].url, "https://example.com/formatb-article1")

    def test_normalize_format_b_maps_snippet(self):
        """_normalize maps 'snippet' field directly in Format B."""
        engine = self._get_engine()
        results = engine._normalize(_SAMPLE_FORMAT_B_RESULTS)
        self.assertEqual(results[0].snippet, "格式B的第一条摘要。")

    def test_normalize_format_b_maps_publish_time(self):
        """_normalize maps 'publish_time' to published_date in Format B."""
        engine = self._get_engine()
        results = engine._normalize(_SAMPLE_FORMAT_B_RESULTS)
        self.assertEqual(results[0].published_date, "2026-04-06")


# ---------------------------------------------------------------------------
# Test class: common _normalize() behavior
# ---------------------------------------------------------------------------


class TestMetasoNormalizeCommon(unittest.TestCase):
    """Test _normalize() behavior shared across both response formats."""

    def _get_engine(self):
        from engines.metaso import MetasoEngine

        return MetasoEngine()

    def test_normalize_score_rank_decay(self):
        """_normalize assigns score as 1.0 / (index + 1)."""
        engine = self._get_engine()
        results = engine._normalize(_SAMPLE_FORMAT_A_RESULTS)
        self.assertAlmostEqual(results[0].score, 1.0)
        self.assertAlmostEqual(results[1].score, 1.0 / 2)
        self.assertAlmostEqual(results[2].score, 1.0 / 3)

    def test_normalize_source_engine(self):
        """_normalize sets source_engine to ['metaso'] for all results."""
        engine = self._get_engine()
        results = engine._normalize(_SAMPLE_FORMAT_A_RESULTS)
        for r in results:
            self.assertEqual(r.source_engine, ["metaso"])

    def test_normalize_empty_results(self):
        """_normalize returns empty list for empty input."""
        engine = self._get_engine()
        results = engine._normalize([])
        self.assertEqual(results, [])


# ---------------------------------------------------------------------------
# Test class: full search with Format B response
# ---------------------------------------------------------------------------


class TestMetasoSearchFormatB(unittest.TestCase):
    """Test that search() correctly handles Format B API response."""

    @patch("engines.metaso.urlopen")
    def test_search_format_b_returns_results(self, mock_urlopen):
        """search() correctly parses Format B response."""
        resp = _MockHTTPResponse(200, _sample_response_format_b())
        mock_urlopen.return_value = resp

        from engines.metaso import MetasoEngine

        engine = MetasoEngine()
        results = engine.search("test", config={"api_key": "mk-test-key"})

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].title, "Format B 结果一")
        self.assertEqual(results[0].snippet, "格式B的第一条摘要。")
        self.assertEqual(results[0].published_date, "2026-04-06")
        self.assertEqual(results[0].source_engine, ["metaso"])


# ---------------------------------------------------------------------------
# Test class: freshness parameter
# ---------------------------------------------------------------------------


class TestMetasoFreshness(unittest.TestCase):
    """Test freshness parameter is passed into the request body."""

    def _get_engine(self):
        from engines.metaso import MetasoEngine

        return MetasoEngine()

    @patch("engines.metaso.urlopen")
    def test_freshness_in_body(self, mock_urlopen):
        """freshness='pd' is included in the POST body."""
        resp = _MockHTTPResponse(200, _sample_response_format_a())
        mock_urlopen.return_value = resp

        engine = self._get_engine()
        engine.search("test", freshness="pd", config={"api_key": "mk-test-key"})

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        body = json.loads(request_obj.data.decode("utf-8"))
        self.assertEqual(body["freshness"], "pd")

    @patch("engines.metaso.urlopen")
    def test_freshness_pw_in_body(self, mock_urlopen):
        """freshness='pw' is included in the POST body."""
        resp = _MockHTTPResponse(200, _sample_response_format_a())
        mock_urlopen.return_value = resp

        engine = self._get_engine()
        engine.search("test", freshness="pw", config={"api_key": "mk-test-key"})

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        body = json.loads(request_obj.data.decode("utf-8"))
        self.assertEqual(body["freshness"], "pw")

    @patch("engines.metaso.urlopen")
    def test_no_freshness_omitted_from_body(self, mock_urlopen):
        """When freshness is None, no freshness key in the POST body."""
        resp = _MockHTTPResponse(200, _sample_response_format_a())
        mock_urlopen.return_value = resp

        engine = self._get_engine()
        engine.search("test", freshness=None, config={"api_key": "mk-test-key"})

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        body = json.loads(request_obj.data.decode("utf-8"))
        self.assertNotIn("freshness", body)


# ---------------------------------------------------------------------------
# Test class: empty results from API
# ---------------------------------------------------------------------------


class TestMetasoEmptyResults(unittest.TestCase):
    """Test behavior when API returns no results."""

    @patch("engines.metaso.urlopen")
    def test_empty_format_a_returns_empty_list(self, mock_urlopen):
        """search() returns empty list when Format A has no results."""
        resp = _MockHTTPResponse(200, {"data": {"results": []}})
        mock_urlopen.return_value = resp

        from engines.metaso import MetasoEngine

        engine = MetasoEngine()
        results = engine.search("不存在的内容", config={"api_key": "mk-test-key"})

        self.assertEqual(results, [])
        self.assertIsInstance(results, list)

    @patch("engines.metaso.urlopen")
    def test_empty_format_b_returns_empty_list(self, mock_urlopen):
        """search() returns empty list when Format B has no results."""
        resp = _MockHTTPResponse(200, {"items": []})
        mock_urlopen.return_value = resp

        from engines.metaso import MetasoEngine

        engine = MetasoEngine()
        results = engine.search("不存在的内容", config={"api_key": "mk-test-key"})

        self.assertEqual(results, [])
        self.assertIsInstance(results, list)


# ---------------------------------------------------------------------------
# Test class: is_available
# ---------------------------------------------------------------------------


class TestMetasoIsAvailable(unittest.TestCase):
    """Test is_available inherits correctly from BaseEngine."""

    def test_available_with_key(self):
        from engines.metaso import MetasoEngine

        engine = MetasoEngine()
        self.assertTrue(engine.is_available({"api_key": "mk-valid-key"}))

    def test_not_available_without_key(self):
        from engines.metaso import MetasoEngine

        engine = MetasoEngine()
        self.assertFalse(engine.is_available({}))

    def test_not_available_with_empty_key(self):
        from engines.metaso import MetasoEngine

        engine = MetasoEngine()
        self.assertFalse(engine.is_available({"api_key": ""}))

    def test_not_available_with_whitespace_key(self):
        from engines.metaso import MetasoEngine

        engine = MetasoEngine()
        self.assertFalse(engine.is_available({"api_key": "   "}))


if __name__ == "__main__":
    unittest.main()
