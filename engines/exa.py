"""Exa AI search engine implementation.

Uses the Exa search API (https://api.exa.ai/search) to retrieve web results.
Requires an API key passed via config["api_key"].
"""

import json
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import logging

logger = logging.getLogger(__name__)

from engines.base import BaseEngine, SearchResult

_ENDPOINT = "https://api.exa.ai/search"


class ExaEngine(BaseEngine):
    """Search engine backed by the Exa AI API."""

    name: str = "exa"
    display_name: str = "Exa AI"
    priority: int = 1
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
        """Execute a search against the Exa API.

        Args:
            query: Search query string.
            max_results: Maximum number of results to return.
            freshness: Freshness filter — "pd" (today), "pw" (this week),
                       "pm" (this month), or None for no filter.
            config: Dict containing at least {"api_key": "..."}.

        Returns:
            List of SearchResult objects.

        Raises:
            ValueError: If api_key is missing or empty.
            HTTPError: If the Exa API returns a non-200 response.
        """
        api_key = self._resolve_api_key(config)
        body = self._build_request_body(query, max_results, freshness)

        request = Request(
            _ENDPOINT,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
            },
            method="POST",
        )

        try:
            with urlopen(request) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
        except HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            logger.warning("Exa API error %s: %s", exc.code, detail)
            raise RuntimeError(
                f"Exa API HTTP {exc.code}: {detail or str(exc)}"
            ) from exc

        return self._normalize(raw.get("results", []))

    # ------------------------------------------------------------------
    # Normalization
    # ------------------------------------------------------------------

    def _normalize(self, raw_results) -> List[SearchResult]:
        """Convert Exa API response items into SearchResult objects."""
        results: List[SearchResult] = []
        for index, item in enumerate(raw_results):
            snippet = self._extract_snippet(item)
            # Use native score when present in response, otherwise rank decay
            score = item["score"] if "score" in item else 1.0 / (index + 1)
            results.append(
                SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=snippet,
                    source_engine=["exa"],
                    published_date=item.get("publishedDate"),
                    score=score,
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
        """Build the JSON request body for the Exa API."""
        body: dict = {
            "query": query,
            "type": "auto",
            "numResults": max_results,
            "contents": {
                "highlights": {"maxCharacters": 4000}
            },
        }

        if freshness in ("pd", "pw", "pm"):
            body["startPublishedDate"] = ExaEngine._freshness_to_date(freshness)

        return body

    @staticmethod
    def _freshness_to_date(freshness: str) -> str:
        """Convert a freshness shorthand to an ISO 8601 date string.

        Args:
            freshness: One of "pd", "pw", "pm".

        Returns:
            Date string in YYYY-MM-DD format.
        """
        now = datetime.now(timezone.utc)

        if freshness == "pd":
            return now.strftime("%Y-%m-%d")

        if freshness == "pw":
            monday = now - timedelta(days=now.weekday())
            return monday.strftime("%Y-%m-%d")

        if freshness == "pm":
            return now.replace(day=1).strftime("%Y-%m-%d")

        # Should not reach here if caller checks freshness value.
        return now.strftime("%Y-%m-%d")

    @staticmethod
    def _extract_snippet(item: dict) -> str:
        """Extract a snippet from an Exa result item.

        Priority: highlights joined by newline > text truncated to 400 chars > empty string.
        """
        highlights = item.get("highlights")
        if highlights:
            return "\n".join(highlights)

        text = item.get("text", "")
        if text and len(text) > 400:
            return text[:400]
        return text if text else ""
