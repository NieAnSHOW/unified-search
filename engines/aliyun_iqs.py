"""Aliyun IQS (夸克) search engine implementation.

Uses the Aliyun Intelligent Query Service (IQS) unified search API.
Requires an API key passed via config["api_key"].
"""

import json
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from urllib.request import Request, urlopen

from engines.base import BaseEngine, SearchResult

_ENDPOINT = "https://cloud-iqs.aliyuncs.com/search/unified"
_DEFAULT_ENGINE_TYPE = "LiteAdvanced"


class AliyunIQSEngine(BaseEngine):
    """Search engine backed by Aliyun IQS (夸克) API."""

    name: str = "aliyun_iqs"
    display_name: str = "Aliyun IQS (夸克)"
    priority: int = 4
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
        """Execute a search against the Aliyun IQS API.

        Args:
            query: Search query string.
            max_results: Maximum number of results to return.
            freshness: Freshness filter — "pd" (today), "pw" (this week),
                       "pm" (this month), or None for no filter.
            config: Dict containing at least {"api_key": "..."}.
                    Optionally {"engine_type": "..."} to override default.

        Returns:
            List of SearchResult objects.

        Raises:
            ValueError: If api_key is missing or empty.
            HTTPError: If the API returns a non-200 response.
        """
        api_key = self._resolve_api_key(config)
        engine_type = (
            config.get("engine_type", _DEFAULT_ENGINE_TYPE)
            if config
            else _DEFAULT_ENGINE_TYPE
        )
        body = self._build_request_body(query, max_results, freshness, engine_type)

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

        return self._normalize(raw.get("pageItems", []))

    # ------------------------------------------------------------------
    # Normalization
    # ------------------------------------------------------------------

    def _normalize(self, raw_results) -> List[SearchResult]:
        """Convert Aliyun IQS API response items into SearchResult objects."""
        results: List[SearchResult] = []
        for rank, item in enumerate(raw_results):
            score = item.get("rerankScore")
            if score is None:
                # Rank-based decay: 1/(rank+1)
                score = 1.0 / (rank + 1)

            published_time = item.get("publishedTime")
            if published_time is not None and not published_time.strip():
                published_time = None

            snippet = item.get("snippet", "")
            if not snippet:
                snippet = item.get("mainText", "")

            results.append(
                SearchResult(
                    title=item.get("title", ""),
                    url=item.get("link", ""),
                    snippet=snippet,
                    source_engine=["aliyun_iqs"],
                    published_date=published_time,
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
        engine_type: str,
    ) -> dict:
        """Build the JSON request body for the Aliyun IQS API."""
        body: dict = {
            "query": query,
            "engine": engine_type,
            "count": max_results,
        }

        if freshness in ("pd", "pw", "pm"):
            body["startDate"] = AliyunIQSEngine._freshness_to_date(freshness)

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
