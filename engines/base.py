"""Base engine abstractions for unified-search.

Provides SearchResult dataclass and BaseEngine abstract base class
that all search engine implementations must extend.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class SearchResult:
    """A unified search result from one or more engines."""

    title: str
    url: str
    snippet: str
    source_engine: List[str]
    published_date: Optional[str] = None
    score: float = 0.0


class BaseEngine(ABC):
    """Abstract base class for all search engines.

    Subclasses must implement:
      - search(query, max_results, freshness) -> List[SearchResult]
      - _normalize(raw_results) -> List[SearchResult]
    """

    name: str = ""
    display_name: str = ""
    priority: int = 100
    requires_key: bool = False

    @abstractmethod
    def search(
        self,
        query: str,
        max_results: int = 10,
        freshness: Optional[str] = None,
    ) -> List[SearchResult]:
        """Execute a search and return unified SearchResult list."""

    @abstractmethod
    def _normalize(self, raw_results) -> List[SearchResult]:
        """Convert engine-specific raw response into SearchResult list."""

    def is_available(self, config: dict) -> bool:
        """Check if this engine is usable given the provided config.

        Returns True if:
          - requires_key is False, or
          - requires_key is True and a non-empty api_key exists in config.
        """
        if not self.requires_key:
            return True
        api_key = config.get("api_key", "")
        return bool(api_key and api_key.strip())
