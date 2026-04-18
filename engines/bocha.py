"""Bocha (博查) search engine implementation.

Uses the Bocha Web Search API (https://api.bocha.cn/v1/web-search) to retrieve
web results. Response format is compatible with Bing Search API. Requires an
API key passed via config["api_key"].
"""

import json
from typing import List, Optional
from urllib.request import Request, urlopen

from engines.base import BaseEngine, SearchResult

_ENDPOINT = "https://api.bocha.cn/v1/web-search"

_FRESHNESS_MAP = {
    "pd": "oneDay",
    "pw": "oneWeek",
    "pm": "oneMonth",
    "py": "oneYear",
}


class BochaEngine(BaseEngine):
    """Search engine backed by the Bocha (博查) API."""

    name: str = "bocha"
    display_name: str = "Bocha (博查)"
    priority: int = 4
    requires_key: bool = True

    def search(
        self,
        query: str,
        max_results: int = 10,
        freshness: Optional[str] = None,
        *,
        config: Optional[dict] = None,
    ) -> List[SearchResult]:
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

    def _normalize(self, raw_results) -> List[SearchResult]:
        results: List[SearchResult] = []
        for index, item in enumerate(raw_results):
            results.append(
                SearchResult(
                    title=item.get("name", ""),
                    url=item.get("url", ""),
                    snippet=item.get("snippet", ""),
                    source_engine=["bocha"],
                    published_date=item.get("dateLastCrawled"),
                    score=1.0 / (index + 1),
                )
            )
        return results

    @staticmethod
    def _resolve_api_key(config: Optional[dict]) -> str:
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
        body: dict = {
            "query": query,
            "count": max_results,
            "summary": True,
        }
        if freshness is not None:
            mapped = _FRESHNESS_MAP.get(freshness)
            if mapped:
                body["freshness"] = mapped
        return body

    @staticmethod
    def _extract_results(raw: dict) -> list:
        return raw.get("data", {}).get("webPages", {}).get("value", [])
