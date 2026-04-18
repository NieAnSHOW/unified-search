"""Metaso (秘塔) search engine implementation.

Uses the Metaso Search API (https://metaso.cn/api/v1/search) to retrieve web
results. Requires an API key passed via config["api_key"].

Supports two possible response formats:
  - Format A: {"data": {"results": [{"title", "url", "content", "date"}]}}
  - Format B: {"items": [{"title", "url", "snippet", "publish_time"}]}
"""

import json
from typing import List, Optional
from urllib.request import Request, urlopen

from engines.base import BaseEngine, SearchResult

_ENDPOINT = "https://metaso.cn/api/v1/search"


class MetasoEngine(BaseEngine):
    """Search engine backed by the Metaso (秘塔) API."""

    name: str = "metaso"
    display_name: str = "Metaso (秘塔)"
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
        """Execute a search against the Metaso API.

        Args:
            query: Search query string.
            max_results: Maximum number of results to return.
            freshness: Optional freshness filter passed to the API
                       (e.g. "pd", "pw", "pm", "py").
            config: Dict containing at least {"api_key": "..."}.

        Returns:
            List of SearchResult objects.

        Raises:
            ValueError: If api_key is missing or empty.
            HTTPError: If the Metaso API returns a non-200 response.
        """
        api_key = self._resolve_api_key(config)
        body = self._build_request_body(query, max_results, freshness)

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

        raw_results = self._extract_results(raw)
        return self._normalize(raw_results)

    # ------------------------------------------------------------------
    # Normalization
    # ------------------------------------------------------------------

    def _normalize(self, raw_results) -> List[SearchResult]:
        """Convert Metaso API response items into SearchResult objects.

        Handles both response formats:
          - Format A items have keys: title, url, content, date
          - Format B items have keys: title, url, snippet, publish_time

        Score is assigned by rank decay: 1.0 / (index + 1).
        source_engine is always ["metaso"].
        """
        results: List[SearchResult] = []
        for index, item in enumerate(raw_results):
            title = item.get("title", "")
            url = item.get("url", "")
            snippet = self._extract_snippet(item)
            published_date = self._extract_date(item)

            results.append(
                SearchResult(
                    title=title,
                    url=url,
                    snippet=snippet,
                    source_engine=["metaso"],
                    published_date=published_date,
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
    def _build_request_body(
        query: str,
        max_results: int,
        freshness: Optional[str],
    ) -> dict:
        """Build the JSON request body for the Metaso API."""
        body: dict = {
            "query": query,
            "scope": "webpage",
        }
        if freshness is not None:
            body["freshness"] = freshness
        return body

    @staticmethod
    def _extract_results(raw: dict) -> list:
        """Extract the results list from the raw API response.

        Supports both Format A (data.results) and Format B (items).
        Returns an empty list if neither format is detected.
        """
        # Format A: {"data": {"results": [...]}}
        if "data" in raw and isinstance(raw["data"], dict):
            results = raw["data"].get("results", [])
            if isinstance(results, list):
                return results

        # Format B: {"items": [...]}
        if "items" in raw and isinstance(raw["items"], list):
            return raw["items"]

        # Fallback: return empty list
        return []

    @staticmethod
    def _extract_snippet(item: dict) -> str:
        """Extract snippet text from a result item.

        Format A uses 'content', Format B uses 'snippet'.
        """
        return item.get("content") or item.get("snippet") or ""

    @staticmethod
    def _extract_date(item: dict) -> Optional[str]:
        """Extract the published date from a result item.

        Format A uses 'date', Format B uses 'publish_time'.
        """
        return item.get("date") or item.get("publish_time") or None
