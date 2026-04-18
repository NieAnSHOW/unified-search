"""Tavily search engine implementation.

Uses the Tavily Search API (https://api.tavily.com/search) to retrieve web results.
Requires an API key passed via config["api_key"].
"""

import json
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from engines.base import BaseEngine, SearchResult

_ENDPOINT = "https://api.tavily.com/search"

# Freshness mapping: freshness code -> number of days
_FRESHNESS_DAYS = {
    "pd": 1,
    "pw": 7,
    "pm": 30,
}


class TavilyEngine(BaseEngine):
    """Search engine backed by the Tavily Search API."""

    name: str = "tavily"
    display_name: str = "Tavily"
    priority: int = 3
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
        """Execute a search against the Tavily API.

        Args:
            query: Search query string.
            max_results: Maximum number of results to return.
            freshness: Freshness filter -- "pd" (day), "pw" (week),
                       "pm" (month), or None for no filter.
            config: Dict containing at least {"api_key": "..."}.

        Returns:
            List of SearchResult objects.

        Raises:
            ValueError: If api_key is missing or empty.
            HTTPError: If the Tavily API returns a non-200 response.
        """
        api_key = self._resolve_api_key(config)
        body = self._build_request_body(query, max_results, freshness, config)

        request = Request(
            _ENDPOINT,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )

        with urlopen(request) as resp:
            raw = json.loads(resp.read().decode("utf-8"))

        return self._normalize(raw.get("results", []))

    # ------------------------------------------------------------------
    # Normalization
    # ------------------------------------------------------------------

    def _normalize(self, raw_results) -> List[SearchResult]:
        """Convert Tavily API response items into SearchResult objects.

        Maps:
          - title -> title
          - url -> url
          - content -> snippet
          - score -> score (native Tavily score)
          - published_date -> published_date
          - source_engine always ["tavily"]
        """
        results: List[SearchResult] = []
        for item in raw_results:
            results.append(
                SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("content", ""),
                    source_engine=["tavily"],
                    published_date=item.get("published_date"),
                    score=item.get("score", 0.0),
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
    def _build_request_body(
        query: str,
        max_results: int,
        freshness: Optional[str],
        config: Optional[dict],
    ) -> dict:
        """Build the JSON request body for the Tavily API.

        Args:
            query: Search query string.
            max_results: Maximum number of results.
            freshness: Optional freshness filter code (pd/pw/pm).
            config: Optional config dict with search_depth and include_answer.

        Returns:
            Dict representing the Tavily API request body.
        """
        body: dict = {
            "query": query,
            "max_results": max_results,
            "search_depth": config.get("search_depth", "basic") if config else "basic",
            "include_answer": config.get("include_answer", False) if config else False,
            "include_raw_content": False,
        }

        if freshness in _FRESHNESS_DAYS:
            days = _FRESHNESS_DAYS[freshness]
            start_date = datetime.now(timezone.utc) - timedelta(days=days)
            body["start_date"] = start_date.strftime("%Y-%m-%d")

        return body
