"""DuckDuckGo search engine implementation.

Uses the DuckDuckGo HTML endpoint (https://html.duckduckgo.com/html/)
to retrieve web results via HTML scraping. No API key required.
"""

import re
from html.parser import HTMLParser
from typing import List, Optional
from urllib.parse import parse_qs, unquote, urlencode
from urllib.request import Request, urlopen

from engines.base import BaseEngine, SearchResult

_ENDPOINT = "https://html.duckduckgo.com/html/"

_FRESHNESS_MAP = {
    "day": "d",
    "week": "w",
    "month": "m",
}

_UDDG_RE = re.compile(r"uddg=([^&]+)")


# ---------------------------------------------------------------------------
# HTML Parser for DuckDuckGo results
# ---------------------------------------------------------------------------


class _DuckDuckGoHTMLParser(HTMLParser):
    """Parses DuckDuckGo HTML search results.

    Extracts results from:
      - <a class="result__a" href="...">Title</a>
      - <a class="result__snippet" href="...">Snippet</a>

    The parser collects raw (title, url, snippet) tuples and returns them
    after feed() completes.
    """

    def __init__(self):
        super().__init__()
        self._results: list = []  # list of (title, url, snippet) tuples
        self._current_title = ""
        self._current_url = ""
        self._in_title_anchor = False
        self._in_snippet_anchor = False
        self._snippet_text = ""

    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)

        # Detect title anchor: <a class="result__a" href="...">
        if tag == "a":
            classes = attr_dict.get("class", "")
            if "result__a" in classes:
                self._in_title_anchor = True
                self._current_title = ""
                self._current_url = attr_dict.get("href", "")
            elif "result__snippet" in classes:
                self._in_snippet_anchor = True
                self._snippet_text = ""

    def handle_endtag(self, tag):
        if tag == "a":
            if self._in_title_anchor:
                self._in_title_anchor = False
                # When the title anchor closes, we have a complete result entry.
                # The snippet may or may not have been seen yet.
                self._results.append(
                    (self._current_title, self._current_url, None)
                )
            elif self._in_snippet_anchor:
                self._in_snippet_anchor = False
                # Attach snippet to the most recent result
                if self._results:
                    title, url, _ = self._results[-1]
                    self._results[-1] = (title, url, self._snippet_text)

    def handle_data(self, data):
        if self._in_title_anchor:
            self._current_title += data
        elif self._in_snippet_anchor:
            self._snippet_text += data

    @property
    def results(self) -> list:
        """Return parsed (title, url, snippet) tuples."""
        return self._results


# ---------------------------------------------------------------------------
# Engine implementation
# ---------------------------------------------------------------------------


class DuckDuckGoEngine(BaseEngine):
    """Search engine backed by DuckDuckGo HTML scraping."""

    name: str = "duckduckgo"
    display_name: str = "DuckDuckGo"
    priority: int = 6
    requires_key: bool = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        max_results: int = 10,
        freshness: Optional[str] = None,
        *,
        config: Optional[dict] = None,
    ) -> List[SearchResult]:
        """Execute a search against DuckDuckGo HTML endpoint.

        Args:
            query: Search query string.
            max_results: Maximum number of results to return.
            freshness: Freshness filter -- "day", "week", "month",
                       or None for no filter.
            config: Ignored (no API key needed).

        Returns:
            List of SearchResult objects.
        """
        url = self._build_url(query, freshness)

        request = Request(url, method="GET")

        with urlopen(request) as resp:
            raw_html = resp.read().decode("utf-8")

        all_results = self._normalize(raw_html)
        return all_results[:max_results]

    # ------------------------------------------------------------------
    # Normalization
    # ------------------------------------------------------------------

    def _normalize(self, raw_results) -> List[SearchResult]:
        """Parse DuckDuckGo HTML into SearchResult objects.

        Args:
            raw_results: Raw HTML string from DuckDuckGo.

        Returns:
            List of SearchResult objects with cleaned URLs and rank-decay scores.
        """
        if not raw_results or not isinstance(raw_results, str):
            return []

        parser = _DuckDuckGoHTMLParser()
        try:
            parser.feed(raw_results)
        except Exception:
            # Tolerate malformed HTML -- return whatever we have so far
            pass

        results: List[SearchResult] = []
        for index, (title, url, snippet) in enumerate(parser.results):
            cleaned_url = self._clean_url(url)
            results.append(
                SearchResult(
                    title=title.strip(),
                    url=cleaned_url,
                    snippet=(snippet or "").strip(),
                    source_engine=["duckduckgo"],
                    published_date=None,
                    score=1.0 / (index + 1),
                )
            )

        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_url(query: str, freshness: Optional[str]) -> str:
        """Build the full DuckDuckGo HTML search URL.

        Args:
            query: Search query string.
            freshness: Optional freshness filter (day/week/month).

        Returns:
            Full URL string with encoded query parameters.
        """
        params = {"q": query}
        df_value = _FRESHNESS_MAP.get(freshness or "")
        if df_value:
            params["df"] = df_value

        return f"{_ENDPOINT}?{urlencode(params)}"

    @staticmethod
    def _clean_url(href: str) -> str:
        """Extract real URL from DuckDuckGo redirect URL.

        DDG uses redirect URLs like:
          //duckduckgo.com/l/?uddg=ENCODED_URL&rut=...

        This method extracts and decodes the uddg parameter.
        If the URL doesn't match the redirect pattern, it's returned as-is.

        Args:
            href: The href attribute value from the anchor tag.

        Returns:
            Cleaned URL string.
        """
        if not href:
            return ""

        match = _UDDG_RE.search(href)
        if match:
            encoded_url = match.group(1)
            # URL-decode the uddg value (may be double-encoded)
            return unquote(encoded_url)

        # Not a redirect URL -- return as-is
        return href
