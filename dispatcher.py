"""Dispatcher for unified-search.

Orchestrates parallel search across multiple engines, merges results,
and provides a CLI interface.

Usage:
    python3 dispatcher.py "search query"
    python3 dispatcher.py "search query" --freshness pw
    python3 dispatcher.py "search query" --engines exa,querit
    python3 dispatcher.py "search query" --max-results 5
    python3 dispatcher.py "search query" --compact
"""

import argparse
import importlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor, wait as futures_wait
from pathlib import Path
from typing import Dict, List, Optional, Type

from config_loader import load_config, get_engine_config, get_enabled_engines
from engines.base import BaseEngine
from merger import merge_results


# ---------------------------------------------------------------------------
# Module name -> class name mapping
# ---------------------------------------------------------------------------

def _module_name_to_class_name(module_name: str) -> str:
    """Convert a module filename to the expected Engine class name.

    Rules:
      - exa          -> ExaEngine
      - duckduckgo   -> DuckDuckGoEngine
      - aliyun_iqs   -> AliyunIqsEngine

    For camelCase-like names (no underscores), capitalize the first letter
    and append "Engine". For snake_case names, capitalize each part.
    """
    parts = module_name.split("_")
    if len(parts) == 1:
        # No underscores — just capitalize first letter + "Engine"
        return parts[0].capitalize() + "Engine"
    else:
        # Snake case — capitalize each part and join + "Engine"
        return "".join(part.capitalize() for part in parts) + "Engine"


# ---------------------------------------------------------------------------
# Dynamic engine discovery
# ---------------------------------------------------------------------------

_ENGINES_DIR = Path(__file__).resolve().parent / "engines"


def _discover_engine_classes() -> List[Type[BaseEngine]]:
    """Scan engines/ directory and dynamically import engine classes.

    Returns a list of BaseEngine subclasses found in non-__init__ .py modules
    under the engines/ directory. Looks for any concrete BaseEngine subclass
    in each module (does not rely on naming convention).
    """
    classes: List[Type[BaseEngine]] = []

    if not _ENGINES_DIR.is_dir():
        return classes

    for filename in sorted(_ENGINES_DIR.iterdir()):
        if filename.name.startswith("_") or not filename.suffix == ".py":
            continue

        module_name = filename.stem  # e.g. "exa", "duckduckgo"
        full_module = f"engines.{module_name}"

        try:
            module = importlib.import_module(full_module)
        except Exception:
            # Skip modules that fail to import (missing deps, etc.)
            continue

        # Scan all attributes for BaseEngine subclasses
        for attr_name in dir(module):
            attr = getattr(module, attr_name, None)
            if attr is None:
                continue
            if not isinstance(attr, type):
                continue
            try:
                if issubclass(attr, BaseEngine) and attr is not BaseEngine:
                    classes.append(attr)
            except TypeError:
                pass

    return classes


def _instantiate_engines(engine_classes: List[Type[BaseEngine]]) -> List[BaseEngine]:
    """Instantiate each engine class (no-arg constructor)."""
    return [cls() for cls in engine_classes]


# ---------------------------------------------------------------------------
# get_available_engines
# ---------------------------------------------------------------------------

def get_available_engines(config: dict) -> List[BaseEngine]:
    """Discover, instantiate, and filter engines that are available.

    Args:
        config: Full configuration dict (from load_config).

    Returns:
        List of BaseEngine instances that are both enabled in config
        and pass their is_available() check.
    """
    enabled_names = set(get_enabled_engines(config))
    if not enabled_names:
        return []

    engine_classes = _discover_engine_classes()
    engines = _instantiate_engines(engine_classes)

    available: List[BaseEngine] = []
    for engine in engines:
        if engine.name not in enabled_names:
            continue
        engine_config = get_engine_config(config, engine.name)
        if engine.is_available(engine_config):
            available.append(engine)

    return available


# ---------------------------------------------------------------------------
# search_parallel
# ---------------------------------------------------------------------------

def search_parallel(
    query: str,
    engines: List[BaseEngine],
    config: dict,
    max_results: int = 10,
    freshness: Optional[str] = None,
    timeout: int = 10,
) -> dict:
    """Execute searches across all engines in parallel.

    Args:
        query: Search query string.
        engines: List of BaseEngine instances to query.
        config: Full configuration dict (engine configs extracted internally).
        max_results: Maximum results per engine.
        freshness: Freshness filter string (e.g. "pw", "7d").
        timeout: Per-engine timeout in seconds.

    Returns:
        dict with keys:
          - "results": {engine_name: [SearchResult], ...}
          - "failed": [engine_name, ...]
    """
    results: Dict[str, list] = {}
    failed: List[str] = []

    def _call_engine(engine: BaseEngine) -> tuple:
        """Call a single engine and return (name, results_or_None)."""
        engine_config = get_engine_config(config, engine.name)
        try:
            res = engine.search(
                query,
                max_results=max_results,
                freshness=freshness,
                config=engine_config,
            )
            return (engine.name, res)
        except Exception:
            return (engine.name, None)

    if not engines:
        return {"results": results, "failed": failed}

    with ThreadPoolExecutor(max_workers=len(engines)) as executor:
        future_map = {
            executor.submit(_call_engine, engine): engine
            for engine in engines
        }

        # Use a generous overall timeout to allow all futures to complete,
        # but enforce per-future timeout.
        done, not_done = futures_wait(
            future_map, timeout=timeout + 1
        )

        for future in done:
            engine = future_map[future]
            try:
                name, res = future.result(timeout=0)
                if res is not None:
                    results[name] = res
                else:
                    failed.append(name)
            except Exception:
                failed.append(engine.name)

        for future in not_done:
            engine = future_map[future]
            failed.append(engine.name)
            future.cancel()

    return {"results": results, "failed": failed}


# ---------------------------------------------------------------------------
# main() — CLI entry point
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the CLI."""
    parser = argparse.ArgumentParser(
        prog="dispatcher.py",
        description="Unified search dispatcher — query multiple engines in parallel.",
    )
    parser.add_argument(
        "query",
        type=str,
        help="Search query string.",
    )
    parser.add_argument(
        "--freshness",
        type=str,
        default=None,
        help="Freshness filter (e.g. pw, 7d, 1m).",
    )
    parser.add_argument(
        "--engines",
        type=str,
        default=None,
        help="Comma-separated list of engines to use (e.g. exa,querit).",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=10,
        help="Maximum results per engine (default: 10).",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        default=False,
        help="Omit snippet and published_date from output.",
    )
    return parser


def _serialize_results(merged: dict, compact: bool = False) -> dict:
    """Convert merged results (which may contain dataclass objects) to JSON-safe dict.

    Args:
        merged: Output from merge_results().
        compact: If True, omit snippet and published_date from each result.

    Returns:
        A JSON-serializable dict.
    """
    import dataclasses

    output = {
        "query": merged.get("query", ""),
        "timestamp": merged.get("timestamp", ""),
        "engines_used": merged.get("engines_used", []),
        "engines_failed": merged.get("engines_failed", []),
        "total_results": merged.get("total_results", 0),
        "overall_confidence": merged.get("overall_confidence", "low"),
        "results": [],
    }

    for result in merged.get("results", []):
        if dataclasses.is_dataclass(result):
            item = dataclasses.asdict(result)
        elif isinstance(result, dict):
            item = dict(result)
        else:
            continue

        if compact:
            item.pop("snippet", None)
            item.pop("published_date", None)

        output["results"].append(item)

    return output


def main() -> int:
    """CLI entry point.

    Returns:
        Exit code: 0 = success (2+ engines), 1 = partial (1 engine), 2 = failure.
    """
    parser = _build_parser()
    args = parser.parse_args()

    # Load config
    try:
        config = load_config()
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stdout)
        return 2

    # Discover available engines
    all_available = get_available_engines(config)

    # Filter by --engines if specified
    if args.engines:
        requested = [e.strip() for e in args.engines.split(",")]
        all_available = [e for e in all_available if e.name in requested]

    if not all_available:
        print(json.dumps({
            "query": args.query,
            "timestamp": "",
            "engines_used": [],
            "engines_failed": [],
            "total_results": 0,
            "overall_confidence": "low",
            "results": [],
            "error": "No available engines",
        }))
        return 2

    # Execute parallel search
    timeout = config.get("timeout_seconds", 10)
    parallel_result = search_parallel(
        args.query,
        all_available,
        config,
        max_results=args.max_results,
        freshness=args.freshness,
        timeout=timeout,
    )

    # Merge results
    merged = merge_results(
        parallel_result["results"],
        query=args.query,
        freshness=args.freshness,
    )
    # Add failed engines from parallel step that are not already in merged
    existing_failed = set(merged.get("engines_failed", []))
    for name in parallel_result["failed"]:
        if name not in existing_failed:
            merged.setdefault("engines_failed", []).append(name)
    merged["engines_failed"] = sorted(merged.get("engines_failed", []))

    # Serialize and output
    output = _serialize_results(merged, compact=args.compact)
    print(json.dumps(output, ensure_ascii=False, indent=2))

    # Determine exit code based on number of engines that returned results
    engines_used_count = len(merged.get("engines_used", []))
    if engines_used_count >= 2:
        return 0
    elif engines_used_count == 1:
        return 1
    else:
        return 2


if __name__ == "__main__":
    sys.exit(main())
