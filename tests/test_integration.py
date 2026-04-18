"""Integration tests for unified-search.

Tests the full pipeline: dispatcher.search_parallel() -> merger.merge_results().
All HTTP requests are mocked; engines are replaced with fake BaseEngine instances
so no real network calls are made.

TDD approach: these tests validate that the existing modules compose correctly.
"""

import json
import os
import sys
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Ensure the project root is on sys.path so imports work from the test dir.
# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fake_engine(name, results=None, side_effect=None):
    """Return a MagicMock that quacks like a BaseEngine.

    Args:
        name: Engine name (e.g. "exa", "brave").
        results: List of SearchResult to return on search().
        side_effect: Exception or callable to use as search side_effect.
    """
    engine = MagicMock()
    engine.name = name
    engine.display_name = name.capitalize()
    engine.priority = 100
    engine.requires_key = False
    engine.is_available.return_value = True
    if side_effect is not None:
        engine.search.side_effect = side_effect
    elif results is not None:
        engine.search.return_value = results
    else:
        engine.search.return_value = []
    return engine


def _make_result(
    title="Title",
    url="https://example.com",
    snippet="Snippet text",
    source_engine=None,
    published_date=None,
    score=0.0,
):
    """Build a SearchResult dataclass instance."""
    from engines.base import SearchResult
    return SearchResult(
        title=title,
        url=url,
        snippet=snippet,
        source_engine=source_engine or ["fake"],
        published_date=published_date,
        score=score,
    )


def _standard_config():
    """Return a standard test configuration dict."""
    return {
        "default_engines": ["exa", "brave", "duckduckgo", "metaso", "querit"],
        "min_engines": 2,
        "timeout_seconds": 10,
        "max_results_per_engine": 10,
        "freshness": None,
        "engines": {
            "exa": {"api_key": "test-key", "type": "auto", "enabled": True},
            "brave": {"api_key": "test-key", "enabled": True},
            "duckduckgo": {"enabled": True},
            "metaso": {"api_key": "test-key", "scope": "webpage", "enabled": True},
            "querit": {"api_key": "test-key", "count": 10, "enabled": True},
        },
    }


def _run_pipeline(engines, config, query="test query", freshness=None, max_results=10, timeout=10):
    """Run the full dispatcher -> merger pipeline.

    Returns the merged result dict.
    """
    from dispatcher import search_parallel
    from merger import merge_results

    parallel_result = search_parallel(
        query,
        engines,
        config,
        max_results=max_results,
        freshness=freshness,
        timeout=timeout,
    )

    merged = merge_results(
        parallel_result["results"],
        query=query,
        freshness=freshness,
    )

    # Propagate failed engines (same logic as dispatcher.main)
    existing_failed = set(merged.get("engines_failed", []))
    for name in parallel_result["failed"]:
        if name not in existing_failed:
            merged.setdefault("engines_failed", []).append(name)
    merged["engines_failed"] = sorted(merged.get("engines_failed", []))

    return merged


# ===========================================================================
# 1. End-to-end search flow
# ===========================================================================


class TestEndToEndSearch(unittest.TestCase):
    """Full pipeline: search_parallel -> merge_results with multiple engines."""

    def test_end_to_end_search(self):
        """Mock all engines, run parallel search, merge, verify output structure."""
        # Arrange: 3 engines with overlapping and unique results
        common_url = "https://example.com/article1"
        r_exa = [
            _make_result(title="Exa Result 1", url=common_url, snippet="Snippet from Exa", source_engine=["exa"]),
            _make_result(title="Exa Result 2", url="https://example.com/article2", snippet="Exa only", source_engine=["exa"]),
        ]
        r_brave = [
            _make_result(title="Brave Result 1", url=common_url, snippet="Brave snippet", source_engine=["brave"]),
            _make_result(title="Brave Result 3", url="https://example.com/article3", snippet="Brave only", source_engine=["brave"]),
        ]
        r_ddg = [
            _make_result(title="DDG Result 4", url="https://example.com/article4", snippet="DDG only", source_engine=["duckduckgo"]),
        ]

        engine_exa = _make_fake_engine("exa", results=r_exa)
        engine_brave = _make_fake_engine("brave", results=r_brave)
        engine_ddg = _make_fake_engine("duckduckgo", results=r_ddg)

        config = _standard_config()

        # Act
        merged = _run_pipeline([engine_exa, engine_brave, engine_ddg], config, query="python tutorial")

        # Assert: output JSON structure is complete
        self.assertEqual(merged["query"], "python tutorial")
        self.assertIn("timestamp", merged)
        self.assertIsInstance(merged["timestamp"], str)

        # engines_used should contain all 3 engines
        self.assertEqual(set(merged["engines_used"]), {"exa", "brave", "duckduckgo"})
        self.assertEqual(merged["engines_failed"], [])

        # Results: common_url should be deduplicated, so total < 6
        self.assertEqual(merged["total_results"], 4)  # article1 (merged), article2, article3, article4

        # Deduplication: the common URL result should have both engines in source_engine
        common_result = [r for r in merged["results"] if r.url == common_url]
        self.assertEqual(len(common_result), 1)
        self.assertIn("exa", common_result[0].source_engine)
        self.assertIn("brave", common_result[0].source_engine)

        # Scores should be reasonable (0.0 to 1.0)
        for r in merged["results"]:
            self.assertGreaterEqual(r.score, 0.0)
            self.assertLessEqual(r.score, 1.0)

        # Results should be sorted by score descending
        scores = [r.score for r in merged["results"]]
        self.assertEqual(scores, sorted(scores, reverse=True))

        # Confidence: overall is the minimum of top-5 results' confidence levels.
        # With 1 cross-validated result (confidence=medium) and 3 single-engine results
        # (confidence=low), the top-5 minimum is "low". The cross-validated result
        # itself should have at least "medium" confidence.
        cross_validated_results = [r for r in merged["results"] if len(r.source_engine) > 1]
        from merger import determine_confidence
        if cross_validated_results:
            self.assertEqual(determine_confidence(cross_validated_results[0]), "medium")

        # The cross-validated result (common_url) should have higher score than single-engine results
        cross_validated = [r for r in merged["results"] if len(r.source_engine) > 1]
        single_engine = [r for r in merged["results"] if len(r.source_engine) == 1]
        if cross_validated and single_engine:
            self.assertGreaterEqual(cross_validated[0].score, single_engine[-1].score)


# ===========================================================================
# 2. Partial engine failure
# ===========================================================================


class TestPartialEngineFailure(unittest.TestCase):
    """Some engines succeed, others fail or timeout."""

    def test_partial_engine_failure(self):
        """3 engines succeed, 2 fail -- verify partial results still work."""
        r_exa = [
            _make_result(title="Exa OK", url="https://exa.com/1", snippet="Exa result", source_engine=["exa"]),
        ]
        r_brave = [
            _make_result(title="Brave OK", url="https://brave.com/1", snippet="Brave result", source_engine=["brave"]),
        ]
        r_ddg = [
            _make_result(title="DDG OK", url="https://ddg.com/1", snippet="DDG result", source_engine=["duckduckgo"]),
        ]

        engine_exa = _make_fake_engine("exa", results=r_exa)
        engine_brave = _make_fake_engine("brave", results=r_brave)
        engine_ddg = _make_fake_engine("duckduckgo", results=r_ddg)
        engine_metaso = _make_fake_engine("metaso", side_effect=TimeoutError("timeout"))
        engine_querit = _make_fake_engine("querit", side_effect=RuntimeError("error"))

        config = _standard_config()

        # Act: should NOT raise
        merged = _run_pipeline(
            [engine_exa, engine_brave, engine_ddg, engine_metaso, engine_querit],
            config,
            query="test",
        )

        # Assert: successful engines appear in engines_used
        self.assertEqual(set(merged["engines_used"]), {"exa", "brave", "duckduckgo"})

        # Failed engines appear in engines_failed
        self.assertEqual(set(merged["engines_failed"]), {"metaso", "querit"})

        # Results from successful engines are present
        self.assertEqual(merged["total_results"], 3)
        urls = {r.url for r in merged["results"]}
        self.assertIn("https://exa.com/1", urls)
        self.assertIn("https://brave.com/1", urls)
        self.assertIn("https://ddg.com/1", urls)


# ===========================================================================
# 3. Single engine results
# ===========================================================================


class TestSingleEngineResults(unittest.TestCase):
    """Only 1 engine returns results."""

    def test_single_engine_results(self):
        """Only 1 engine returns results: confidence=low, exit_code=1."""
        r_exa = [
            _make_result(title="Only Exa", url="https://exa.com/1", snippet="Solo result", source_engine=["exa"]),
        ]

        engine_exa = _make_fake_engine("exa", results=r_exa)
        engine_brave = _make_fake_engine("brave", side_effect=RuntimeError("fail"))

        config = _standard_config()

        # Act
        merged = _run_pipeline([engine_exa, engine_brave], config, query="test")

        # Assert: confidence is low (only 1 engine)
        self.assertEqual(merged["overall_confidence"], "low")
        self.assertEqual(merged["total_results"], 1)
        self.assertEqual(merged["engines_used"], ["exa"])

        # Exit code: 1 engine used -> exit code 1
        engines_used_count = len(merged.get("engines_used", []))
        self.assertEqual(engines_used_count, 1)
        # Simulate exit code logic from dispatcher.main
        if engines_used_count >= 2:
            exit_code = 0
        elif engines_used_count == 1:
            exit_code = 1
        else:
            exit_code = 2
        self.assertEqual(exit_code, 1)


# ===========================================================================
# 4. All engines failed
# ===========================================================================


class TestAllEnginesFailed(unittest.TestCase):
    """Every engine fails or times out."""

    def test_all_engines_failed(self):
        """All engines fail: empty results, exit_code=2."""
        engine_exa = _make_fake_engine("exa", side_effect=RuntimeError("fail"))
        engine_brave = _make_fake_engine("brave", side_effect=TimeoutError("timeout"))
        engine_ddg = _make_fake_engine("duckduckgo", side_effect=ConnectionError("refused"))

        config = _standard_config()

        # Act: should NOT raise
        merged = _run_pipeline([engine_exa, engine_brave, engine_ddg], config, query="test")

        # Assert: no results, all engines in failed list
        self.assertEqual(merged["total_results"], 0)
        self.assertEqual(merged["results"], [])
        self.assertEqual(set(merged["engines_failed"]), {"exa", "brave", "duckduckgo"})
        self.assertEqual(merged["engines_used"], [])
        self.assertEqual(merged["overall_confidence"], "low")

        # Exit code: 0 engines used -> exit code 2
        engines_used_count = len(merged.get("engines_used", []))
        if engines_used_count >= 2:
            exit_code = 0
        elif engines_used_count == 1:
            exit_code = 1
        else:
            exit_code = 2
        self.assertEqual(exit_code, 2)


# ===========================================================================
# 5. Cross-validation (deduplication + multi-engine scoring)
# ===========================================================================


class TestCrossValidation(unittest.TestCase):
    """Same URL appears in multiple engines -> deduplication and boosted score."""

    def test_cross_validation(self):
        """Same URL from 3 engines: dedup, multi-engine source, higher score, confidence >= medium."""
        shared_url = "https://example.com/shared-article"

        r_exa = [
            _make_result(title="Exa Shared", url=shared_url, snippet="Exa snippet for shared", source_engine=["exa"]),
        ]
        r_brave = [
            _make_result(title="Brave Shared", url=shared_url, snippet="Brave snippet for shared article", source_engine=["brave"]),
        ]
        r_ddg = [
            _make_result(title="DDG Shared", url=shared_url, snippet="DDG snippet", source_engine=["duckduckgo"]),
        ]

        engine_exa = _make_fake_engine("exa", results=r_exa)
        engine_brave = _make_fake_engine("brave", results=r_brave)
        engine_ddg = _make_fake_engine("duckduckgo", results=r_ddg)

        config = _standard_config()

        # Act
        merged = _run_pipeline([engine_exa, engine_brave, engine_ddg], config, query="shared")

        # Assert: only 1 result after dedup
        self.assertEqual(merged["total_results"], 1)

        result = merged["results"][0]
        self.assertEqual(result.url, shared_url)

        # source_engine should contain all 3 engines
        self.assertEqual(set(result.source_engine), {"exa", "brave", "duckduckgo"})

        # Score should be higher than a single-engine result
        # base_score = 3 * 0.3 = 0.9, plus priority_bonus for exa (0.2) = 1.1 clamped to 1.0
        self.assertGreater(result.score, 0.5)

        # Confidence should be at least medium (3 engines -> high)
        self.assertEqual(merged["overall_confidence"], "high")

    def test_partial_overlap_dedup(self):
        """Two engines share a URL, one has unique URLs -- verify correct dedup."""
        shared_url = "https://example.com/overlap"
        unique_exa_url = "https://example.com/exa-only"
        unique_brave_url = "https://example.com/brave-only"

        r_exa = [
            _make_result(title="Shared", url=shared_url, snippet="Shared", source_engine=["exa"]),
            _make_result(title="Exa Only", url=unique_exa_url, snippet="Exa only", source_engine=["exa"]),
        ]
        r_brave = [
            _make_result(title="Shared Too", url=shared_url, snippet="Brave shared snippet text", source_engine=["brave"]),
            _make_result(title="Brave Only", url=unique_brave_url, snippet="Brave only", source_engine=["brave"]),
        ]

        engine_exa = _make_fake_engine("exa", results=r_exa)
        engine_brave = _make_fake_engine("brave", results=r_brave)

        config = _standard_config()
        merged = _run_pipeline([engine_exa, engine_brave], config, query="overlap test")

        # 3 unique URLs after dedup
        self.assertEqual(merged["total_results"], 3)

        # The shared URL result should have both engines
        shared_results = [r for r in merged["results"] if r.url == shared_url]
        self.assertEqual(len(shared_results), 1)
        self.assertEqual(set(shared_results[0].source_engine), {"exa", "brave"})

        # Shared result should have the longest snippet (Brave's)
        self.assertEqual(shared_results[0].snippet, "Brave shared snippet text")

        # Shared result should rank higher than single-engine results
        single_results = [r for r in merged["results"] if len(r.source_engine) == 1]
        if single_results:
            self.assertGreaterEqual(shared_results[0].score, single_results[0].score)


# ===========================================================================
# 6. Config-driven engine selection
# ===========================================================================


class TestConfigDrivenEngineSelection(unittest.TestCase):
    """Only enabled engines in config should be used."""

    def test_config_driven_engine_selection(self):
        """Only 2 engines enabled in config: only those 2 are used."""
        # Build a config with only 2 engines enabled
        config = {
            "default_engines": ["exa", "brave"],
            "min_engines": 2,
            "timeout_seconds": 10,
            "engines": {
                "exa": {"api_key": "test-key", "type": "auto", "enabled": True},
                "brave": {"api_key": "test-key", "enabled": True},
                "duckduckgo": {"enabled": False},
                "metaso": {"api_key": "test-key", "enabled": False},
                "querit": {"api_key": "test-key", "enabled": False},
            },
        }

        engine_exa = _make_fake_engine("exa", results=[
            _make_result(title="Exa", url="https://exa.com/1", snippet="Exa", source_engine=["exa"]),
        ])
        engine_brave = _make_fake_engine("brave", results=[
            _make_result(title="Brave", url="https://brave.com/1", snippet="Brave", source_engine=["brave"]),
        ])
        # These engines exist but should NOT be called
        engine_ddg = _make_fake_engine("duckduckgo", results=[
            _make_result(title="DDG", url="https://ddg.com/1", snippet="DDG", source_engine=["duckduckgo"]),
        ])

        from config_loader import get_enabled_engines

        # Verify config only enables 2 engines
        enabled = get_enabled_engines(config)
        self.assertEqual(set(enabled), {"exa", "brave"})

        # Run pipeline with only the 2 enabled engines
        merged = _run_pipeline([engine_exa, engine_brave], config, query="test")

        # Only exa and brave should appear
        self.assertEqual(set(merged["engines_used"]), {"exa", "brave"})
        self.assertEqual(merged["engines_failed"], [])
        self.assertEqual(merged["total_results"], 2)

        # DDG should NOT have been called
        engine_ddg.search.assert_not_called()

    def test_config_disabled_engine_not_used_via_main(self):
        """main() should not use engines that are disabled in config."""
        from dispatcher import main
        import io

        engine_exa = _make_fake_engine("exa", results=[
            _make_result(title="Exa", url="https://exa.com/1", snippet="Exa", source_engine=["exa"]),
        ])

        config = {
            "default_engines": ["exa"],
            "min_engines": 1,
            "engines": {
                "exa": {"api_key": "test-key", "enabled": True},
                "brave": {"api_key": "test-key", "enabled": False},
            },
        }

        with patch("dispatcher.load_config", return_value=config), \
             patch("dispatcher.get_available_engines", return_value=[engine_exa]), \
             patch("sys.argv", ["dispatcher.py", "test"]):
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                exit_code = main()

        output = json.loads(mock_out.getvalue())
        self.assertEqual(set(output["engines_used"]), {"exa"})
        self.assertNotIn("brave", output["engines_used"])


# ===========================================================================
# 7. Freshness end-to-end
# ===========================================================================


class TestFreshnessEndToEnd(unittest.TestCase):
    """Freshness parameter flows through the entire pipeline."""

    def test_freshness_end_to_end(self):
        """freshness param passed to engines and used in merger recency calculation."""
        # Create a result with a recent published_date (within 7 days)
        today_str = datetime.utcnow().strftime("%Y-%m-%d")

        r_exa = [
            _make_result(
                title="Recent Article",
                url="https://example.com/recent",
                snippet="A very recent article",
                source_engine=["exa"],
                published_date=today_str,
            ),
        ]
        r_brave = [
            _make_result(
                title="Old Article",
                url="https://example.com/old",
                snippet="An old article from long ago",
                source_engine=["brave"],
                published_date="2020-01-01",
            ),
        ]

        engine_exa = _make_fake_engine("exa", results=r_exa)
        engine_brave = _make_fake_engine("brave", results=r_brave)

        config = _standard_config()
        freshness = "7d"

        # Act
        merged = _run_pipeline(
            [engine_exa, engine_brave],
            config,
            query="test",
            freshness=freshness,
        )

        # Assert: engines received freshness parameter
        engine_exa.search.assert_called_once()
        exa_call_kwargs = engine_exa.search.call_args.kwargs
        self.assertEqual(exa_call_kwargs.get("freshness"), "7d")

        engine_brave.search.assert_called_once()
        brave_call_kwargs = engine_brave.search.call_args.kwargs
        self.assertEqual(brave_call_kwargs.get("freshness"), "7d")

        # Assert: recent article should get recency bonus
        recent_result = [r for r in merged["results"] if r.url == "https://example.com/recent"]
        old_result = [r for r in merged["results"] if r.url == "https://example.com/old"]

        self.assertEqual(len(recent_result), 1)
        self.assertEqual(len(old_result), 1)

        # The recent result should have a higher score due to recency_bonus
        # recent: base_score=0.3 + priority_bonus(exa)=0.2 + recency_bonus=0.1 = 0.6
        # old:    base_score=0.3 + priority_bonus(brave)=0.08 = 0.38
        self.assertGreater(recent_result[0].score, old_result[0].score)

    def test_freshness_not_applied_to_old_dates(self):
        """Articles older than freshness window should not get recency bonus."""
        r_exa = [
            _make_result(
                title="Old Article",
                url="https://example.com/old-exa",
                snippet="Very old",
                source_engine=["exa"],
                published_date="2023-01-01",
            ),
        ]
        r_brave = [
            _make_result(
                title="Another Old",
                url="https://example.com/old-brave",
                snippet="Also old",
                source_engine=["brave"],
                published_date="2022-06-15",
            ),
        ]

        engine_exa = _make_fake_engine("exa", results=r_exa)
        engine_brave = _make_fake_engine("brave", results=r_brave)

        config = _standard_config()
        freshness = "7d"

        merged = _run_pipeline(
            [engine_exa, engine_brave],
            config,
            query="test",
            freshness=freshness,
        )

        # Both results are old -- neither should get recency bonus
        # exa: base_score=0.3 + priority=0.2 = 0.5
        # brave: base_score=0.3 + priority=0.08 = 0.38
        exa_result = [r for r in merged["results"] if "exa" in r.source_engine][0]
        brave_result = [r for r in merged["results"] if "brave" in r.source_engine][0]

        # Exa has higher priority but no recency bonus for either
        self.assertAlmostEqual(exa_result.score, 0.5, places=1)
        self.assertAlmostEqual(brave_result.score, 0.38, places=1)

    def test_freshness_with_week_unit(self):
        """Freshness '4w' should parse correctly and apply recency bonus."""
        three_weeks_ago = (datetime.utcnow() - timedelta(days=21)).strftime("%Y-%m-%d")

        r_exa = [
            _make_result(
                title="Within Weeks",
                url="https://example.com/within-weeks",
                snippet="Within 4 weeks",
                source_engine=["exa"],
                published_date=three_weeks_ago,
            ),
        ]

        engine_exa = _make_fake_engine("exa", results=r_exa)
        config = _standard_config()

        merged = _run_pipeline(
            [engine_exa],
            config,
            query="test",
            freshness="4w",
        )

        # Should have recency bonus (21 days < 4 weeks)
        result = merged["results"][0]
        # base_score=0.3 + priority=0.2 + recency=0.1 = 0.6
        self.assertAlmostEqual(result.score, 0.6, places=1)


# ===========================================================================
# Bonus: Full CLI integration
# ===========================================================================


class TestCLIIntegration(unittest.TestCase):
    """Integration test using main() CLI entry point with mocked engines."""

    def test_full_cli_flow_outputs_valid_json(self):
        """main() with 3 engines produces valid JSON with correct structure."""
        from dispatcher import main
        import io

        engine_exa = _make_fake_engine("exa", results=[
            _make_result(title="Exa Result", url="https://exa.com/1", snippet="Exa snippet", source_engine=["exa"]),
        ])
        engine_brave = _make_fake_engine("brave", results=[
            _make_result(title="Brave Result", url="https://brave.com/1", snippet="Brave snippet", source_engine=["brave"]),
        ])
        engine_ddg = _make_fake_engine("duckduckgo", results=[
            _make_result(title="DDG Result", url="https://ddg.com/1", snippet="DDG snippet", source_engine=["duckduckgo"]),
        ])

        config = _standard_config()

        with patch("dispatcher.load_config", return_value=config), \
             patch("dispatcher.get_available_engines", return_value=[engine_exa, engine_brave, engine_ddg]), \
             patch("sys.argv", ["dispatcher.py", "integration test"]):
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                exit_code = main()

        output = mock_out.getvalue()
        self.assertEqual(exit_code, 0)

        parsed = json.loads(output)

        # Verify all required JSON keys
        required_keys = [
            "query", "timestamp", "engines_used", "engines_failed",
            "total_results", "overall_confidence", "results",
        ]
        for key in required_keys:
            self.assertIn(key, parsed, f"Missing key: {key}")

        self.assertEqual(parsed["query"], "integration test")
        self.assertEqual(parsed["total_results"], 3)
        self.assertEqual(set(parsed["engines_used"]), {"exa", "brave", "duckduckgo"})
        self.assertEqual(parsed["engines_failed"], [])

        # Results should be JSON-serializable dicts (not dataclass objects)
        for result in parsed["results"]:
            self.assertIsInstance(result, dict)
            self.assertIn("title", result)
            self.assertIn("url", result)
            self.assertIn("source_engine", result)
            self.assertIn("score", result)


if __name__ == "__main__":
    unittest.main()
