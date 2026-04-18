"""Result merger for unified-search.

Combines results from multiple search engines with deduplication,
cross-validation scoring, and confidence determination.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
from urllib.parse import parse_qs, urlencode, urlunparse, urlparse

from engines.base import SearchResult

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TRACKING_PARAMS = frozenset(
    ["utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term"]
)

_ENGINE_PRIORITY = {
    "exa": 0.2,
    "querit": 0.15,
    "metaso": 0.12,
    "aliyun_iqs": 0.10,
    "brave": 0.08,
    "duckduckgo": 0.05,
    "bocha": 0.12,
}

_CONFIDENCE_THRESHOLDS = [
    (3, "high"),
    (2, "medium"),
    (1, "low"),
]

# Map from freshness string suffix to timedelta keyword arguments.
_FRESHNESS_MAP = {
    "d": "days",
    "w": "weeks",
    "m": "months",
    "y": "years",
}


# ---------------------------------------------------------------------------
# URL normalization
# ---------------------------------------------------------------------------

def normalize_url(url: str) -> str:
    """Normalize a URL for deduplication purposes.

    Rules applied:
      - lowercase hostname
      - remove www. prefix
      - remove trailing slash from path
      - remove fragment (#...)
      - remove common tracking params (utm_*)
      - sort remaining query params
    """
    parsed = urlparse(url)

    # Lowercase hostname and strip www.
    hostname = parsed.hostname or ""
    hostname = hostname.lower()
    if hostname.startswith("www."):
        hostname = hostname[4:]

    # Remove trailing slash from path.
    path = parsed.path
    if path.endswith("/") and len(path) > 1:
        path = path.rstrip("/")

    # Parse, filter, and sort query params.
    query_dict = parse_qs(parsed.query, keep_blank_values=True)
    # parse_qs returns lists; flatten to single values, drop tracking params.
    filtered_query: Dict[str, str] = {}
    for key, values in query_dict.items():
        if key in _TRACKING_PARAMS:
            continue
        filtered_query[key] = values[-1]  # keep last occurrence

    sorted_query = urlencode(sorted(filtered_query.items()))

    return urlunparse((
        parsed.scheme,
        hostname,
        path,
        parsed.params,
        sorted_query,
        "",  # no fragment
    ))


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def deduplicate(results: List[SearchResult]) -> List[SearchResult]:
    """Deduplicate results by normalized URL.

    When merging duplicates:
      - Keep the longest title
      - Keep the longest snippet
      - Union source_engine lists (deduplicated)
      - Keep the most recent published_date
      - Keep the maximum score
    """
    groups: Dict[str, List[SearchResult]] = {}
    for result in results:
        key = normalize_url(result.url)
        groups.setdefault(key, []).append(result)

    deduped: List[SearchResult] = []
    for group in groups.values():
        if len(group) == 1:
            deduped.append(group[0])
            continue

        # Merge fields.
        merged_engines: List[str] = []
        for r in group:
            for e in r.source_engine:
                if e not in merged_engines:
                    merged_engines.append(e)

        best_title = max(group, key=lambda r: len(r.title)).title
        best_snippet = max(group, key=lambda r: len(r.snippet)).snippet
        best_score = max(r.score for r in group)

        # Pick the most recent published_date.
        dates = [r.published_date for r in group if r.published_date is not None]
        best_date = max(dates) if dates else None

        deduped.append(SearchResult(
            title=best_title,
            url=group[0].url,
            snippet=best_snippet,
            source_engine=merged_engines,
            published_date=best_date,
            score=best_score,
        ))

    return deduped


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _parse_freshness(freshness: Optional[str]) -> Optional[timedelta]:
    """Parse a freshness string like '7d', '1w', '3m' into a timedelta."""
    if freshness is None:
        return None
    suffix = freshness[-1].lower()
    prefix = freshness[:-1]
    unit = _FRESHNESS_MAP.get(suffix)
    if unit is None:
        return None
    try:
        value = int(prefix)
    except ValueError:
        return None
    if value <= 0:
        return None
    return timedelta(**{unit: value})


def calculate_score(
    result: SearchResult,
    freshness: Optional[str] = None,
) -> float:
    """Calculate cross-validation score for a result.

    Scoring formula:
      base_score = len(source_engine) * 0.3
      priority_bonus = highest priority among source engines
      recency_bonus = 0.1 if published_date within freshness window

    Final score is clamped to [0.0, 1.0].
    """
    base_score = len(result.source_engine) * 0.3

    # Priority bonus: use the highest priority engine in the list.
    priority_bonus = 0.0
    for engine in result.source_engine:
        bonus = _ENGINE_PRIORITY.get(engine, 0.0)
        if bonus > priority_bonus:
            priority_bonus = bonus

    # Recency bonus.
    recency_bonus = 0.0
    freshness_td = _parse_freshness(freshness)
    if freshness_td is not None and result.published_date is not None:
        try:
            pub_date = datetime.strptime(result.published_date, "%Y-%m-%d")
            cutoff = datetime.utcnow() - freshness_td
            if pub_date >= cutoff:
                recency_bonus = 0.1
        except ValueError:
            pass  # unparseable date => no recency bonus

    score = base_score + priority_bonus + recency_bonus
    return max(0.0, min(1.0, score))


# ---------------------------------------------------------------------------
# Confidence
# ---------------------------------------------------------------------------

def determine_confidence(result: SearchResult) -> str:
    """Determine confidence level based on number of source engines.

    - "high": 3+ engines
    - "medium": 2 engines
    - "low": 1 engine or fewer
    """
    count = len(result.source_engine)
    for threshold, label in _CONFIDENCE_THRESHOLDS:
        if count >= threshold:
            return label
    return "low"


# ---------------------------------------------------------------------------
# Main merge function
# ---------------------------------------------------------------------------

def merge_results(
    engine_results: Dict[str, Optional[List[SearchResult]]],
    query: str = "",
    freshness: Optional[str] = None,
) -> dict:
    """Merge results from multiple search engines.

    Args:
        engine_results: Mapping of engine name to its result list (or None if failed).
        query: The original search query.
        freshness: Optional freshness window string (e.g. '7d', '1w').

    Returns:
        A dict with keys:
          - query: the original query string
          - timestamp: ISO 8601 UTC timestamp
          - engines_used: list of engines that returned results
          - engines_failed: list of engines that failed (None or missing)
          - total_results: number of merged results
          - overall_confidence: confidence of the weakest top-5 result
          - results: list of merged SearchResult objects
    """
    # Collect all results and classify engines.
    all_results: List[SearchResult] = []
    engines_used: List[str] = []
    engines_failed: List[str] = []

    for engine_name, results in engine_results.items():
        if results is None:
            engines_failed.append(engine_name)
        else:
            engines_used.append(engine_name)
            all_results.extend(results)

    # Deduplicate.
    deduped = deduplicate(all_results)

    # Calculate scores.
    for result in deduped:
        result.score = calculate_score(result, freshness=freshness)

    # Sort by score descending.
    deduped.sort(key=lambda r: r.score, reverse=True)

    # Determine overall confidence from top-5 (or all if fewer).
    top_results = deduped[:5]
    if top_results:
        confidences = [determine_confidence(r) for r in top_results]
        # Map to numeric levels for comparison.
        conf_rank = {"high": 3, "medium": 2, "low": 1}
        overall = min(confidences, key=lambda c: conf_rank.get(c, 0))
    else:
        overall = "low"

    return {
        "query": query,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "engines_used": sorted(engines_used),
        "engines_failed": sorted(engines_failed),
        "total_results": len(deduped),
        "overall_confidence": overall,
        "results": deduped,
    }
