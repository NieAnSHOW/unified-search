"""Tests for DuckDuckGo search engine.

Follows TDD: these tests define the expected behavior of engines/duckduckgo.py.
All HTTP calls are mocked via urllib.request.urlopen.
"""

import unittest
from unittest.mock import patch

from engines.base import SearchResult


class _MockHTTPResponse:
    """Simulates an HTTPResponse returned by urlopen."""

    def __init__(self, status_code: int, body: str):
        self.status_code = status_code
        self._body = body.encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


# ---------------------------------------------------------------------------
# Sample DuckDuckGo HTML responses
# ---------------------------------------------------------------------------

# Realistic DDG HTML result block structure:
# <div class="result results_links results_links_deep web-result">
#   <div class="links_main links_deep result__body">
#     <h2 class="result__title">
#       <a class="result__a" href="//duckduckgo.com/l/?uddg=ENCODED_URL&rut=...">Title</a>
#     </h2>
#     <a class="result__snippet" href="//duckduckgo.com/l/?uddg=ENCODED_URL&rut=...">Snippet text</a>
#   </div>
# </div>

_SAMPLE_HTML = """<!DOCTYPE html>
<html>
<head><title>DuckDuckGo</title></head>
<body>
<div class="result results_links results_links_deep web-result">
  <div class="links_main links_deep result__body">
    <h2 class="result__title">
      <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Farticle1&amp;rut=abc123">Python Tutorial - Getting Started</a>
    </h2>
    <a class="result__snippet" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Farticle1&amp;rut=abc123">Learn Python programming from scratch with this comprehensive tutorial covering basics to advanced concepts.</a>
  </div>
</div>
<div class="result results_links results_links_deep web-result">
  <div class="links_main links_deep result__body">
    <h2 class="result__title">
      <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Farticle2&amp;rut=def456">Advanced Python Decorators</a>
    </h2>
    <a class="result__snippet" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Farticle2&amp;rut=def456">Deep dive into Python decorators including functools.wraps, class-based decorators, and real-world patterns.</a>
  </div>
</div>
<div class="result results_links results_links_deep web-result">
  <div class="links_main links_deep result__body">
    <h2 class="result__title">
      <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Farticle3&amp;rut=ghi789">Python Async/Await Guide</a>
    </h2>
    <a class="result__snippet" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Farticle3&amp;rut=ghi789">Master asynchronous programming in Python using asyncio, async/await syntax, and concurrent patterns.</a>
  </div>
</div>
</body>
</html>"""

# HTML with a result that has no snippet
_HTML_NO_SNIPPET = """<!DOCTYPE html>
<html>
<head><title>DuckDuckGo</title></head>
<body>
<div class="result results_links results_links_deep web-result">
  <div class="links_main links_deep result__body">
    <h2 class="result__title">
      <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fnosnippet&amp;rut=xyz">Title Only Result</a>
    </h2>
  </div>
</div>
</body>
</html>"""

# Empty HTML - no results
_EMPTY_HTML = """<!DOCTYPE html>
<html>
<head><title>DuckDuckGo</title></head>
<body>
<div class="no-results">No results found.</div>
</body>
</html>"""

# Malformed HTML - broken tags, missing closures
_MALFORMED_HTML = """<!DOCTYPE html>
<html>
<head><title>DuckDuckGo</title></head>
<body>
<div class="result results_links results_links_deep web-result">
  <div class="links_main links_deep result__body">
    <h2 class="result__title">
      <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fmalformed1&amp;rut=bad1">First Malformed Result
    </h2>
    <a class="result__snippet" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fmalformed1&amp;rut=bad1">Snippet for first result</a>
  </div>
</div>
<div class="result results_links results_links_deep web-result">
  <div class="links_main links_deep result__body">
    <h2 class="result__title">
      <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fmalformed2&amp;rut=bad2">Second Malformed Result</a>
      <span class="extra">unexpected nested content</span>
    </h2>
    <a class="result__snippet" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fmalformed2&amp;rut=bad2">Snippet for second result</a>
  </div>
</div>
<div class="result results_links results_links_deep web-result">
  <div class="links_main links_deep result__body">
    <h2 class="result__title">
      <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fmalformed3&amp;rut=bad3">Third Result With
    </a></h2>
    <a class="result__snippet" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fmalformed3&amp;rut=bad3">This has a snippet but title tag is broken
    </a>
  </div>
</div>
</body>
</html>"""

# HTML with URL that has complex query parameters in the redirect
_COMPLEX_REDIRECT_HTML = """<!DOCTYPE html>
<html>
<head><title>DuckDuckGo</title></head>
<body>
<div class="result results_links results_links_deep web-result">
  <div class="links_main links_deep result__body">
    <h2 class="result__title">
      <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fen.wikipedia.org%2Fwiki%2FPython_%28programming_language%29%3Faction%3Dedit%26section%3D5&amp;rut=abc&amp;rut2=def">Wikipedia - Python</a>
    </h2>
    <a class="result__snippet" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fen.wikipedia.org%2Fwiki%2FPython_%28programming_language%29%3Faction%3Dedit%26section%3D5&amp;rut=abc">Python is a high-level, general-purpose programming language.</a>
  </div>
</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Test class: class attributes
# ---------------------------------------------------------------------------


class TestDuckDuckGoEngineAttributes(unittest.TestCase):
    """Test DuckDuckGo engine class attributes match the spec."""

    def test_name(self):
        from engines.duckduckgo import DuckDuckGoEngine

        self.assertEqual(DuckDuckGoEngine.name, "duckduckgo")

    def test_display_name(self):
        from engines.duckduckgo import DuckDuckGoEngine

        self.assertEqual(DuckDuckGoEngine.display_name, "DuckDuckGo")

    def test_priority(self):
        from engines.duckduckgo import DuckDuckGoEngine

        self.assertEqual(DuckDuckGoEngine.priority, 6)

    def test_requires_key(self):
        from engines.duckduckgo import DuckDuckGoEngine

        self.assertFalse(DuckDuckGoEngine.requires_key)


# ---------------------------------------------------------------------------
# Test class: _normalize() field mapping from HTML
# ---------------------------------------------------------------------------


class TestDuckDuckGoNormalize(unittest.TestCase):
    """Test DuckDuckGoEngine._normalize() HTML parsing."""

    def _get_engine(self):
        from engines.duckduckgo import DuckDuckGoEngine

        return DuckDuckGoEngine()

    def test_normalize_returns_search_results(self):
        """_normalize returns a list of SearchResult objects."""
        engine = self._get_engine()
        results = engine._normalize(_SAMPLE_HTML)
        self.assertIsInstance(results, list)
        self.assertEqual(len(results), 3)
        for r in results:
            self.assertIsInstance(r, SearchResult)

    def test_normalize_maps_title(self):
        """_normalize correctly extracts title from result__a anchor."""
        engine = self._get_engine()
        results = engine._normalize(_SAMPLE_HTML)
        self.assertEqual(results[0].title, "Python Tutorial - Getting Started")
        self.assertEqual(results[1].title, "Advanced Python Decorators")
        self.assertEqual(results[2].title, "Python Async/Await Guide")

    def test_normalize_maps_url_from_redirect(self):
        """_normalize extracts real URL from DDG redirect URL's uddg param."""
        engine = self._get_engine()
        results = engine._normalize(_SAMPLE_HTML)
        self.assertEqual(results[0].url, "https://example.com/article1")
        self.assertEqual(results[1].url, "https://example.com/article2")
        self.assertEqual(results[2].url, "https://example.com/article3")

    def test_normalize_maps_snippet(self):
        """_normalize extracts snippet text from result__snippet anchor."""
        engine = self._get_engine()
        results = engine._normalize(_SAMPLE_HTML)
        self.assertEqual(
            results[0].snippet,
            "Learn Python programming from scratch with this comprehensive "
            "tutorial covering basics to advanced concepts.",
        )
        self.assertEqual(
            results[1].snippet,
            "Deep dive into Python decorators including functools.wraps, "
            "class-based decorators, and real-world patterns.",
        )

    def test_normalize_score_rank_decay(self):
        """_normalize assigns score as 1.0 / (index + 1)."""
        engine = self._get_engine()
        results = engine._normalize(_SAMPLE_HTML)
        self.assertAlmostEqual(results[0].score, 1.0)
        self.assertAlmostEqual(results[1].score, 1.0 / 2)
        self.assertAlmostEqual(results[2].score, 1.0 / 3)

    def test_normalize_source_engine(self):
        """_normalize sets source_engine to ['duckduckgo'] for all results."""
        engine = self._get_engine()
        results = engine._normalize(_SAMPLE_HTML)
        for r in results:
            self.assertEqual(r.source_engine, ["duckduckgo"])

    def test_normalize_published_date_none(self):
        """_normalize sets published_date to None (DDG HTML doesn't provide it)."""
        engine = self._get_engine()
        results = engine._normalize(_SAMPLE_HTML)
        for r in results:
            self.assertIsNone(r.published_date)

    def test_normalize_no_snippet_yields_empty_string(self):
        """_normalize uses empty string when snippet anchor is missing."""
        engine = self._get_engine()
        results = engine._normalize(_HTML_NO_SNIPPET)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].snippet, "")

    def test_normalize_empty_html_returns_empty_list(self):
        """_normalize returns empty list for HTML with no results."""
        engine = self._get_engine()
        results = engine._normalize(_EMPTY_HTML)
        self.assertEqual(results, [])


# ---------------------------------------------------------------------------
# Test class: malformed HTML tolerance
# ---------------------------------------------------------------------------


class TestDuckDuckGoMalformedHTML(unittest.TestCase):
    """Test that _normalize tolerates malformed HTML gracefully."""

    def _get_engine(self):
        from engines.duckduckgo import DuckDuckGoEngine

        return DuckDuckGoEngine()

    def test_malformed_html_still_extracts_results(self):
        """_normalize still extracts results from malformed HTML."""
        engine = self._get_engine()
        results = engine._normalize(_MALFORMED_HTML)
        # Should extract at least some results despite broken tags
        self.assertGreaterEqual(len(results), 1)

    def test_malformed_html_does_not_crash(self):
        """_normalize does not raise on malformed HTML."""
        engine = self._get_engine()
        # Should not raise any exception
        try:
            results = engine._normalize(_MALFORMED_HTML)
            self.assertIsInstance(results, list)
        except Exception as e:
            self.fail(f"_normalize raised {e!r} on malformed HTML")

    def test_completely_empty_string(self):
        """_normalize returns empty list for empty string."""
        engine = self._get_engine()
        results = engine._normalize("")
        self.assertEqual(results, [])


# ---------------------------------------------------------------------------
# Test class: URL cleanup
# ---------------------------------------------------------------------------


class TestDuckDuckGoURLCleanup(unittest.TestCase):
    """Test URL extraction from DDG redirect URLs."""

    def _get_engine(self):
        from engines.duckduckgo import DuckDuckGoEngine

        return DuckDuckGoEngine()

    def test_extract_url_with_complex_query_params(self):
        """URL cleanup handles complex query params in the uddg value."""
        engine = self._get_engine()
        results = engine._normalize(_COMPLEX_REDIRECT_HTML)
        self.assertEqual(
            results[0].url,
            "https://en.wikipedia.org/wiki/Python_(programming_language)?action=edit&section=5",
        )

    def test_non_redirect_url_passed_through(self):
        """If URL doesn't match redirect pattern, it's used as-is."""
        engine = self._get_engine()
        # A URL that is not a DDG redirect should pass through unchanged
        html = """<!DOCTYPE html>
<html><body>
<div class="result results_links results_links_deep web-result">
  <div class="links_main links_deep result__body">
    <h2 class="result__title">
      <a class="result__a" href="https://example.com/direct-link">Direct Link</a>
    </h2>
    <a class="result__snippet" href="https://example.com/direct-link">A snippet</a>
  </div>
</div>
</body></html>"""
        results = engine._normalize(html)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].url, "https://example.com/direct-link")

    def test_url_with_missing_uddg_param(self):
        """If redirect URL has no uddg param, falls back to original href."""
        engine = self._get_engine()
        html = """<!DOCTYPE html>
<html><body>
<div class="result results_links results_links_deep web-result">
  <div class="links_main links_deep result__body">
    <h2 class="result__title">
      <a class="result__a" href="//duckduckgo.com/l/?rut=abc123">No uddg param</a>
    </h2>
    <a class="result__snippet" href="//duckduckgo.com/l/?rut=abc123">Snippet</a>
  </div>
</div>
</body></html>"""
        results = engine._normalize(html)
        self.assertEqual(len(results), 1)
        # Should use the full redirect URL as fallback
        self.assertEqual(results[0].url, "//duckduckgo.com/l/?rut=abc123")


# ---------------------------------------------------------------------------
# Test class: search()
# ---------------------------------------------------------------------------


class TestDuckDuckGoSearch(unittest.TestCase):
    """Test DuckDuckGoEngine.search() with mocked HTTP."""

    def _get_engine(self):
        from engines.duckduckgo import DuckDuckGoEngine

        return DuckDuckGoEngine()

    @patch("engines.duckduckgo.urlopen")
    def test_search_returns_search_results(self, mock_urlopen):
        """search() returns a list of SearchResult objects."""
        resp = _MockHTTPResponse(200, _SAMPLE_HTML)
        mock_urlopen.return_value = resp

        engine = self._get_engine()
        results = engine.search("python tutorial")

        self.assertIsInstance(results, list)
        self.assertEqual(len(results), 3)
        for r in results:
            self.assertIsInstance(r, SearchResult)

    @patch("engines.duckduckgo.urlopen")
    def test_search_passes_query(self, mock_urlopen):
        """search() passes the query string as the q URL parameter."""
        resp = _MockHTTPResponse(200, _SAMPLE_HTML)
        mock_urlopen.return_value = resp

        engine = self._get_engine()
        engine.search("python async await")

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        self.assertIn("q=python+async+await", request_obj.full_url)

    @patch("engines.duckduckgo.urlopen")
    def test_search_endpoint(self, mock_urlopen):
        """search() GETs https://html.duckduckgo.com/html/."""
        resp = _MockHTTPResponse(200, _SAMPLE_HTML)
        mock_urlopen.return_value = resp

        engine = self._get_engine()
        engine.search("test")

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        self.assertIn("https://html.duckduckgo.com/html/", request_obj.full_url)
        self.assertEqual(request_obj.method, "GET")

    @patch("engines.duckduckgo.urlopen")
    def test_search_no_api_key_needed(self, mock_urlopen):
        """search() does not require any API key or config."""
        resp = _MockHTTPResponse(200, _SAMPLE_HTML)
        mock_urlopen.return_value = resp

        engine = self._get_engine()
        # Should work without any config parameter
        results = engine.search("test")
        self.assertEqual(len(results), 3)

    @patch("engines.duckduckgo.urlopen")
    def test_search_empty_results(self, mock_urlopen):
        """search() returns empty list when no results in HTML."""
        resp = _MockHTTPResponse(200, _EMPTY_HTML)
        mock_urlopen.return_value = resp

        engine = self._get_engine()
        results = engine.search("nonexistent query xyz123")
        self.assertEqual(results, [])
        self.assertIsInstance(results, list)


# ---------------------------------------------------------------------------
# Test class: freshness parameter
# ---------------------------------------------------------------------------


class TestDuckDuckGoFreshness(unittest.TestCase):
    """Test freshness parameter mapping to df URL query param."""

    def _get_engine(self):
        from engines.duckduckgo import DuckDuckGoEngine

        return DuckDuckGoEngine()

    @patch("engines.duckduckgo.urlopen")
    def test_freshness_day(self, mock_urlopen):
        """freshness='day' passes df=d in URL params."""
        resp = _MockHTTPResponse(200, _SAMPLE_HTML)
        mock_urlopen.return_value = resp

        engine = self._get_engine()
        engine.search("test", freshness="day")

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        self.assertIn("df=d", request_obj.full_url)

    @patch("engines.duckduckgo.urlopen")
    def test_freshness_week(self, mock_urlopen):
        """freshness='week' passes df=w in URL params."""
        resp = _MockHTTPResponse(200, _SAMPLE_HTML)
        mock_urlopen.return_value = resp

        engine = self._get_engine()
        engine.search("test", freshness="week")

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        self.assertIn("df=w", request_obj.full_url)

    @patch("engines.duckduckgo.urlopen")
    def test_freshness_month(self, mock_urlopen):
        """freshness='month' passes df=m in URL params."""
        resp = _MockHTTPResponse(200, _SAMPLE_HTML)
        mock_urlopen.return_value = resp

        engine = self._get_engine()
        engine.search("test", freshness="month")

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        self.assertIn("df=m", request_obj.full_url)

    @patch("engines.duckduckgo.urlopen")
    def test_no_freshness(self, mock_urlopen):
        """When freshness is None, no df param is in the URL."""
        resp = _MockHTTPResponse(200, _SAMPLE_HTML)
        mock_urlopen.return_value = resp

        engine = self._get_engine()
        engine.search("test", freshness=None)

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        self.assertNotIn("df=", request_obj.full_url)

    @patch("engines.duckduckgo.urlopen")
    def test_invalid_freshness_ignored(self, mock_urlopen):
        """When freshness is an unrecognized value, no df param is added."""
        resp = _MockHTTPResponse(200, _SAMPLE_HTML)
        mock_urlopen.return_value = resp

        engine = self._get_engine()
        engine.search("test", freshness="year")

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        self.assertNotIn("df=", request_obj.full_url)


# ---------------------------------------------------------------------------
# Test class: is_available
# ---------------------------------------------------------------------------


class TestDuckDuckGoIsAvailable(unittest.TestCase):
    """Test is_available always returns True (no API key needed)."""

    def test_available_with_empty_config(self):
        from engines.duckduckgo import DuckDuckGoEngine

        engine = DuckDuckGoEngine()
        self.assertTrue(engine.is_available({}))

    def test_available_with_any_config(self):
        from engines.duckduckgo import DuckDuckGoEngine

        engine = DuckDuckGoEngine()
        self.assertTrue(engine.is_available({"api_key": "anything"}))

    def test_available_with_none_config_values(self):
        from engines.duckduckgo import DuckDuckGoEngine

        engine = DuckDuckGoEngine()
        self.assertTrue(engine.is_available({"api_key": ""}))

    def test_available_even_with_empty_dict(self):
        """is_available returns True regardless of config contents."""
        from engines.duckduckgo import DuckDuckGoEngine

        engine = DuckDuckGoEngine()
        self.assertTrue(engine.is_available({}))
        self.assertTrue(engine.is_available({"random": "data"}))


if __name__ == "__main__":
    unittest.main()
