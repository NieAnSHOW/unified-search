"""Querit search engine implementation.

POST https://api.querit.ai/v1/search with Bearer token auth.
Response contains results.result[] with url, title, snippet, page_age, site_name.
Freshness is not supported in the request; instead, page_age is used for
post-filtering in _normalize.
"""

import json
from datetime import datetime, timedelta
from typing import List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from engines.base import BaseEngine, SearchResult

# Freshness mapping: freshness code -> number of days
_FRESHNESS_DAYS = {
    "pd": 1,
    "pw": 7,
    "pm": 30,
}

_API_ENDPOINT = "https://api.querit.ai/v1/search"


class QueritEngine(BaseEngine):
    """Search engine implementation for Querit API."""

    name: str = "querit"
    display_name: str = "Querit"
    priority: int = 2
    requires_key: bool = True

    def search(
        self,
        query: str,
        max_results: int = 10,
        freshness: Optional[str] = None,
        *,
        config: Optional[dict] = None,
    ) -> List[SearchResult]:
        """Execute a search against the Querit API.

        Args:
            query: Search query string.
            max_results: Maximum number of results to return.
            freshness: Freshness filter code (pd/pw/pm). Applied post-fetch
                via page_age filtering.
            config: Dict containing 'api_key' for authentication.

        Returns:
            List of SearchResult objects.

        Raises:
            ValueError: If api_key is missing from config.
            RuntimeError: On API or network errors.
        """
        if not config or not config.get("api_key", "").strip():
            raise ValueError("Querit engine requires 'api_key' in config")

        api_key = config["api_key"].strip()

        payload = json.dumps({"query": query, "count": max_results}).encode("utf-8")

        request = Request(
            _API_ENDPOINT,
            data=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urlopen(request) as response:
                data = json.loads(response.read().decode("utf-8"))
        except HTTPError as e:
            raise RuntimeError(
                f"Querit API error: HTTP {e.code} {e.msg}"
            ) from e
        except URLError as e:
            raise RuntimeError(
                f"Querit API request failed: {e.reason}"
            ) from e

        raw_results = data.get("results", {}).get("result", [])
        if not raw_results:
            return []

        return self._normalize(raw_results, freshness=freshness)

    def _normalize(
        self,
        raw_results: list,
        *,
        freshness: Optional[str] = None,
    ) -> List[SearchResult]:
        """Convert Querit API response items into SearchResult list.

        Applies freshness filtering based on page_age, then assigns
        rank-decay scores.

        Args:
            raw_results: List of raw result dicts from Querit API.
            freshness: Optional freshness filter code (pd/pw/pm).

        Returns:
            Filtered and scored list of SearchResult objects.
        """
        now = datetime.now()
        max_days = _FRESHNESS_DAYS.get(freshness) if freshness else None

        filtered = []
        for item in raw_results:
            page_age = item.get("page_age")
            if max_days is not None and page_age:
                try:
                    pub_date = datetime.strptime(page_age, "%Y-%m-%d")
                    if (now - pub_date).days >= max_days:
                        continue
                except (ValueError, TypeError):
                    # Cannot parse page_age -- keep the result
                    pass
            filtered.append(item)

        results: List[SearchResult] = []
        for index, item in enumerate(filtered):
            results.append(
                SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("snippet", ""),
                    source_engine=["querit"],
                    published_date=item.get("page_age"),
                    score=1.0 / (index + 1),
                )
            )

        return results
