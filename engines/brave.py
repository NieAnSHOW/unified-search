"""Brave Search engine implementation.

Uses the Brave Search Web API (https://api.search.brave.com/res/v1/web/search)
to retrieve web results. Requires an API key passed via config["api_key"].
"""

import json
from typing import List, Optional
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen

from engines.base import BaseEngine, SearchResult

_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"

_VALID_FRESHNESS = {"pd", "pw", "pm", "py"}


class BraveEngine(BaseEngine):
    """Search engine backed by the Brave Search Web API."""

    name: str = "brave"
    display_name: str = "Brave Search"
    priority: int = 5
    requires_key: bool = True

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
        """Execute a search against the Brave Search API.

        Args:
            query: Search query string.
            max_results: Maximum number of results to return (capped at 20).
            freshness: Freshness filter -- "pd" (day), "pw" (week),
                       "pm" (month), "py" (year), or None for no filter.
            config: Dict containing at least {"api_key": "..."}.

        Returns:
            List of SearchResult objects.

        Raises:
            ValueError: If api_key is missing or empty.
            HTTPError: If the Brave API returns a non-200 response.
        """
        api_key = self._resolve_api_key(config)
        url = self._build_url(query, max_results, freshness)

        request = Request(
            url,
            headers={
                "X-Subscription-Token": api_key,
                "Accept": "application/json",
            },
            method="GET",
        )

        with urlopen(request) as resp:
            raw = json.loads(resp.read().decode("utf-8"))

        web_results = raw.get("web", {}).get("results", [])
        return self._normalize(web_results)

    # ------------------------------------------------------------------
    # Normalization
    # ------------------------------------------------------------------

    def _normalize(self, raw_results) -> List[SearchResult]:
        """Convert Brave API response items into SearchResult objects.

        Maps:
          - title -> title
          - url -> url
          - description -> snippet (extra_snippets appended if present)
          - No native score; rank-decay: 1.0 / (index + 1)
          - No published_date in Brave web results
          - source_engine always ["brave"]
        """
        results: List[SearchResult] = []
        for index, item in enumerate(raw_results):
            snippet = self._build_snippet(item)
            results.append(
                SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=snippet,
                    source_engine=["brave"],
                    published_date=None,
                    score=1.0 / (index + 1),
                )
            )
        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_api_key(config: Optional[dict]) -> str:
        """Extract and validate the API key from config.

        Raises:
            ValueError: If config is missing or api_key is empty.
        """
        if not config:
            raise ValueError("config dict with 'api_key' is required")
        api_key = config.get("api_key", "")
        if not api_key or not api_key.strip():
            raise ValueError("config['api_key'] must be a non-empty string")
        return api_key.strip()

    @staticmethod
    def _build_url(query: str, max_results: int, freshness: Optional[str]) -> str:
        """Build the full URL with query parameters.

        Args:
            query: Search query string.
            max_results: Maximum results (capped at 20).
            freshness: Optional freshness filter (pd/pw/pm/py).

        Returns:
            Full URL string with encoded query parameters.
        """
        params = {
            "q": query,
            "count": min(max_results, 20),
        }
        if freshness in _VALID_FRESHNESS:
            params["freshness"] = freshness

        return f"{_ENDPOINT}?{urlencode(params)}"

    @staticmethod
    def _build_snippet(item: dict) -> str:
        """Build snippet from description + extra_snippets.

        Joins the description with any extra_snippets using a space.
        """
        parts = []
        description = item.get("description", "")
        if description:
            parts.append(description)

        extra = item.get("extra_snippets")
        if extra:
            parts.extend(extra)

        return " ".join(parts)
