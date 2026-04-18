# dashboard.py — 统计部分（后续 Task 会扩展此文件）
"""Dashboard server for unified-search.

Provides a web UI for monitoring engine health, testing searches,
and viewing session statistics.

Usage:
    python3 dashboard.py [--port 9728]
"""

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse, parse_qs

from config_loader import load_config, get_engine_config, get_enabled_engines
from dispatcher import get_available_engines, search_parallel
from merger import merge_results
from engines.base import BaseEngine

import dataclasses


class DashboardStats:
    """In-memory session statistics for the dashboard."""

    def __init__(self, max_recent: int = 20):
        self.total_searches: int = 0
        self.recent_queries: List[str] = []
        self.last_confidence: Optional[str] = None
        self.engine_calls: Dict[str, int] = {}
        self.engine_failures: Dict[str, int] = {}
        self.engine_response_times: Dict[str, float] = {}
        self._max_recent = max_recent

    def record_search(
        self,
        query: str,
        engines_used: List[str],
        engines_failed: List[str],
        avg_response_time: float,
        confidence: str,
        response_times: Dict[str, float],
    ):
        self.total_searches += 1
        self.recent_queries.append(query)
        if len(self.recent_queries) > self._max_recent:
            self.recent_queries = self.recent_queries[-self._max_recent:]
        self.last_confidence = confidence

        for name in engines_used:
            self.engine_calls[name] = self.engine_calls.get(name, 0) + 1
        for name in engines_failed:
            self.engine_failures[name] = self.engine_failures.get(name, 0) + 1

        self.engine_response_times.update(response_times)

    def to_dict(self) -> dict:
        return {
            "total_searches": self.total_searches,
            "recent_queries": self.recent_queries,
            "last_confidence": self.last_confidence,
            "engine_calls": dict(self.engine_calls),
            "engine_failures": dict(self.engine_failures),
            "engine_response_times": dict(self.engine_response_times),
        }


def check_engine_health(
    engine: BaseEngine,
    config: dict,
    timeout: float = 5.0,
    slow_threshold: float = 2.0,
) -> dict:
    """Check a single engine's health by doing a lightweight search.

    Returns a dict with: name, status (healthy/slow/error/disabled), latency_ms, error.
    """
    engine_config = get_engine_config(config, engine.name)

    if not engine_config.get("enabled", False):
        return {
            "name": engine.name,
            "display_name": engine.display_name or engine.name,
            "status": "disabled",
            "latency_ms": 0,
            "error": None,
        }

    if not engine.is_available(engine_config):
        return {
            "name": engine.name,
            "display_name": engine.display_name or engine.name,
            "status": "disabled",
            "latency_ms": 0,
            "error": None,
        }

    try:
        start = time.monotonic()
        engine.search(
            "hello world",
            max_results=1,
            config=engine_config,
        )
        elapsed = time.monotonic() - start
        status = "slow" if elapsed > slow_threshold else "healthy"
        return {
            "name": engine.name,
            "display_name": engine.display_name or engine.name,
            "status": status,
            "latency_ms": round(elapsed * 1000, 0),
            "error": None,
        }
    except Exception as exc:
        return {
            "name": engine.name,
            "display_name": engine.display_name or engine.name,
            "status": "error",
            "latency_ms": 0,
            "error": str(exc),
        }


class DashboardHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the dashboard."""

    stats: DashboardStats
    config: dict

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            self._serve_html()
        elif path == "/api/health":
            self._handle_health()
        elif path == "/api/search":
            self._handle_search(parsed)
        elif path == "/api/stats":
            self._handle_stats()
        elif path == "/api/restart":
            self._handle_restart()
        elif path == "/api/stop":
            self._handle_stop()
        else:
            self._send_json({"error": "not found"}, status=404)

    def _serve_html(self):
        html_path = Path(__file__).resolve().parent / "dashboard.html"
        if not html_path.is_file():
            self._send_json({"error": "dashboard.html not found"}, status=500)
            return
        html = html_path.read_text(encoding="utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def _handle_health(self):
        from dispatcher import _discover_engine_classes, _instantiate_engines
        all_instances = _instantiate_engines(_discover_engine_classes())

        results = []
        with ThreadPoolExecutor(max_workers=len(all_instances)) as executor:
            future_map = {
                executor.submit(check_engine_health, engine, self.config): engine
                for engine in all_instances
            }
            for future in future_map:
                try:
                    results.append(future.result(timeout=10))
                except Exception:
                    engine = future_map[future]
                    results.append({
                        "name": engine.name,
                        "status": "error",
                        "latency_ms": 0,
                        "error": "health check timeout",
                    })

        # Update stats with latest response times
        for r in results:
            if r["status"] == "healthy" and r["latency_ms"] > 0:
                self.stats.engine_response_times[r["name"]] = r["latency_ms"]

        self._send_json(results)

    def _handle_search(self, parsed):
        params = parse_qs(parsed.query)
        query_list = params.get("q", [])
        if not query_list or not query_list[0].strip():
            self._send_json({"error": "missing query parameter 'q'"}, status=400)
            return

        query = query_list[0].strip()
        engines = get_available_engines(self.config)

        # Filter by engine param if provided
        engine_filter = params.get("engines", [None])[0]
        if engine_filter:
            requested = [e.strip() for e in engine_filter.split(",")]
            engines = [e for e in engines if e.name in requested]

        if not engines:
            self._send_json({"error": "No available engines"}, status=503)
            return

        timeout = self.config.get("timeout_seconds", 10)
        start = time.monotonic()

        parallel_result = search_parallel(
            query, engines, self.config, max_results=10, timeout=timeout,
        )

        merged = merge_results(
            parallel_result["results"],
            query=query,
        )
        # Add failed engines
        existing_failed = set(merged.get("engines_failed", []))
        for name in parallel_result["failed"]:
            if name not in existing_failed:
                merged.setdefault("engines_failed", []).append(name)

        elapsed = time.monotonic() - start

        # Record response times per engine
        response_times = {}
        for name in merged.get("engines_used", []):
            response_times[name] = round(elapsed * 1000, 0)

        # Record stats
        self.stats.record_search(
            query=query,
            engines_used=merged.get("engines_used", []),
            engines_failed=merged.get("engines_failed", []),
            avg_response_time=round(elapsed * 1000, 0),
            confidence=merged.get("overall_confidence", "low"),
            response_times=response_times,
        )

        # Serialize results
        output = {
            "query": merged.get("query", ""),
            "timestamp": merged.get("timestamp", ""),
            "engines_used": merged.get("engines_used", []),
            "engines_failed": merged.get("engines_failed", []),
            "total_results": merged.get("total_results", 0),
            "overall_confidence": merged.get("overall_confidence", "low"),
            "elapsed_ms": round(elapsed * 1000, 0),
            "results": [],
        }
        for result in merged.get("results", []):
            if dataclasses.is_dataclass(result):
                output["results"].append(dataclasses.asdict(result))
            elif isinstance(result, dict):
                output["results"].append(result)

        self._send_json(output)

    def _handle_stats(self):
        self._send_json(self.stats.to_dict())

    def _handle_restart(self):
        self._send_json({"status": "restarting"})
        server = self.server

        def _do_restart():
            time.sleep(0.5)
            server.shutdown()
            os.execv(sys.executable, [sys.executable] + sys.argv)

        threading.Thread(target=_do_restart, daemon=True).start()

    def _handle_stop(self):
        self._send_json({"status": "stopping"})
        server = self.server

        def _do_stop():
            time.sleep(0.5)
            server.shutdown()

        threading.Thread(target=_do_stop, daemon=True).start()

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass  # Suppress default stderr logging


def create_app(stats: DashboardStats, config: dict, port: int = 9728):
    """Create an HTTPServer instance for the dashboard."""
    handler = type("Handler", (DashboardHandler,), {
        "stats": stats,
        "config": config,
    })
    class ReusableHTTPServer(HTTPServer):
        allow_reuse_address = True
    server = ReusableHTTPServer(("127.0.0.1", port), handler)
    return server


def main():
    parser = argparse.ArgumentParser(
        prog="dashboard.py",
        description="Unified Search Dashboard — web UI for monitoring and testing.",
    )
    parser.add_argument(
        "--port", type=int, default=9728, help="Port to listen on (default: 9728)"
    )
    args = parser.parse_args()

    try:
        config = load_config()
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}))
        sys.exit(1)

    stats = DashboardStats()
    server = create_app(stats, config, port=args.port)
    print(f"Unified Search Dashboard: http://127.0.0.1:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
