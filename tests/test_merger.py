"""Tests for merger module: URL normalization, deduplication, scoring, confidence, and merge."""

import unittest
from datetime import datetime, timedelta
from typing import List

# Lazy import helper so tests can be written before implementation
def _get_merger():
    from merger import (
        normalize_url,
        deduplicate,
        calculate_score,
        determine_confidence,
        merge_results,
    )
    return normalize_url, deduplicate, calculate_score, determine_confidence, merge_results


def _make_result(
    title="Title",
    url="https://example.com",
    snippet="Snippet",
    source_engine=None,
    published_date=None,
    score=0.0,
):
    from engines.base import SearchResult
    return SearchResult(
        title=title,
        url=url,
        snippet=snippet,
        source_engine=source_engine or [],
        published_date=published_date,
        score=score,
    )


# ---------------------------------------------------------------------------
# normalize_url
# ---------------------------------------------------------------------------
class TestNormalizeUrl(unittest.TestCase):
    """Test URL normalization rules."""

    def _get(self):
        funcs = _get_merger()
        return funcs[0]  # normalize_url

    # --- trailing slash ---
    def test_remove_trailing_slash(self):
        normalize_url = self._get()
        self.assertEqual(
            normalize_url("https://example.com/path/"),
            "https://example.com/path",
        )

    def test_keep_path_without_trailing_slash(self):
        normalize_url = self._get()
        self.assertEqual(
            normalize_url("https://example.com/path"),
            "https://example.com/path",
        )

    # --- sort query params ---
    def test_sort_query_params(self):
        normalize_url = self._get()
        self.assertEqual(
            normalize_url("https://example.com?z=1&a=2&m=3"),
            "https://example.com?a=2&m=3&z=1",
        )

    # --- lowercase hostname ---
    def test_lowercase_hostname(self):
        normalize_url = self._get()
        self.assertEqual(
            normalize_url("https://EXAMPLE.COM/path"),
            "https://example.com/path",
        )

    def test_mixed_case_hostname(self):
        normalize_url = self._get()
        self.assertEqual(
            normalize_url("https://ExAmPlE.Com/path"),
            "https://example.com/path",
        )

    # --- remove www. prefix ---
    def test_remove_www_prefix(self):
        normalize_url = self._get()
        self.assertEqual(
            normalize_url("https://www.example.com/path"),
            "https://example.com/path",
        )

    def test_keep_non_www_hostname(self):
        normalize_url = self._get()
        self.assertEqual(
            normalize_url("https://example.com/path"),
            "https://example.com/path",
        )

    # --- remove fragment ---
    def test_remove_fragment(self):
        normalize_url = self._get()
        self.assertEqual(
            normalize_url("https://example.com/path#section"),
            "https://example.com/path",
        )

    def test_remove_fragment_with_query(self):
        normalize_url = self._get()
        self.assertEqual(
            normalize_url("https://example.com/path?a=1#section"),
            "https://example.com/path?a=1",
        )

    # --- remove tracking params ---
    def test_remove_utm_source(self):
        normalize_url = self._get()
        self.assertEqual(
            normalize_url("https://example.com?utm_source=google&a=1"),
            "https://example.com?a=1",
        )

    def test_remove_utm_medium(self):
        normalize_url = self._get()
        self.assertEqual(
            normalize_url("https://example.com?utm_medium=email&a=1"),
            "https://example.com?a=1",
        )

    def test_remove_utm_campaign(self):
        normalize_url = self._get()
        self.assertEqual(
            normalize_url("https://example.com?utm_campaign=spring&a=1"),
            "https://example.com?a=1",
        )

    def test_remove_utm_content(self):
        normalize_url = self._get()
        self.assertEqual(
            normalize_url("https://example.com?utm_content=header&a=1"),
            "https://example.com?a=1",
        )

    def test_remove_utm_term(self):
        normalize_url = self._get()
        self.assertEqual(
            normalize_url("https://example.com?utm_term=shoes&a=1"),
            "https://example.com?a=1",
        )

    def test_remove_multiple_utm_params(self):
        normalize_url = self._get()
        self.assertEqual(
            normalize_url(
                "https://example.com?utm_source=g&utm_medium=m&utm_campaign=c&keep=1"
            ),
            "https://example.com?keep=1",
        )

    # --- combined ---
    def test_combined_normalization(self):
        normalize_url = self._get()
        self.assertEqual(
            normalize_url(
                "https://WWW.Example.COM/path/?utm_source=tw#frag?z=1&a=2"
            ),
            "https://example.com/path",
        )

    def test_url_with_all_features(self):
        normalize_url = self._get()
        self.assertEqual(
            normalize_url(
                "https://www.Google.com/search?q=test&utm_source=tw&b=2&a=1#top/"
            ),
            "https://google.com/search?a=1&b=2&q=test",
        )

    # --- edge cases ---
    def test_plain_url_unchanged(self):
        normalize_url = self._get()
        self.assertEqual(
            normalize_url("https://example.com"),
            "https://example.com",
        )

    def test_url_with_only_tracking_params(self):
        normalize_url = self._get()
        self.assertEqual(
            normalize_url("https://example.com?utm_source=google"),
            "https://example.com",
        )


# ---------------------------------------------------------------------------
# deduplicate
# ---------------------------------------------------------------------------
class TestDeduplicate(unittest.TestCase):
    """Test deduplication of search results by normalized URL."""

    def _get(self):
        funcs = _get_merger()
        return funcs[1]  # deduplicate

    def test_no_duplicates(self):
        dedup = self._get()
        results = [
            _make_result(url="https://a.com/1", source_engine=["exa"]),
            _make_result(url="https://b.com/2", source_engine=["querit"]),
        ]
        deduped = dedup(results)
        self.assertEqual(len(deduped), 2)

    def test_exact_same_url_deduped(self):
        dedup = self._get()
        results = [
            _make_result(url="https://example.com", source_engine=["exa"]),
            _make_result(url="https://example.com", source_engine=["querit"]),
        ]
        deduped = dedup(results)
        self.assertEqual(len(deduped), 1)
        self.assertIn("exa", deduped[0].source_engine)
        self.assertIn("querit", deduped[0].source_engine)

    def test_trailing_slash_deduped(self):
        dedup = self._get()
        results = [
            _make_result(url="https://example.com/path", source_engine=["exa"]),
            _make_result(url="https://example.com/path/", source_engine=["querit"]),
        ]
        deduped = dedup(results)
        self.assertEqual(len(deduped), 1)

    def test_www_prefix_deduped(self):
        dedup = self._get()
        results = [
            _make_result(url="https://example.com/page", source_engine=["exa"]),
            _make_result(url="https://www.example.com/page", source_engine=["brave"]),
        ]
        deduped = dedup(results)
        self.assertEqual(len(deduped), 1)

    def test_tracking_params_deduped(self):
        dedup = self._get()
        results = [
            _make_result(url="https://example.com/a", source_engine=["exa"]),
            _make_result(url="https://example.com/a?utm_source=tw", source_engine=["brave"]),
        ]
        deduped = dedup(results)
        self.assertEqual(len(deduped), 1)

    def test_keeps_longest_title(self):
        dedup = self._get()
        results = [
            _make_result(title="Short", url="https://example.com", source_engine=["exa"]),
            _make_result(
                title="Much Longer Title Here", url="https://example.com", source_engine=["querit"]
            ),
        ]
        deduped = dedup(results)
        self.assertEqual(deduped[0].title, "Much Longer Title Here")

    def test_keeps_longest_snippet(self):
        dedup = self._get()
        results = [
            _make_result(snippet="Short", url="https://example.com", source_engine=["exa"]),
            _make_result(
                snippet="This is a much longer snippet with more detail",
                url="https://example.com",
                source_engine=["querit"],
            ),
        ]
        deduped = dedup(results)
        self.assertEqual(deduped[0].snippet, "This is a much longer snippet with more detail")

    def test_merges_source_engine_deduped(self):
        dedup = self._get()
        results = [
            _make_result(url="https://example.com", source_engine=["exa"]),
            _make_result(url="https://example.com", source_engine=["exa", "querit"]),
        ]
        deduped = dedup(results)
        self.assertEqual(sorted(deduped[0].source_engine), ["exa", "querit"])

    def test_keeps_most_recent_published_date(self):
        dedup = self._get()
        results = [
            _make_result(
                url="https://example.com",
                source_engine=["exa"],
                published_date="2025-01-01",
            ),
            _make_result(
                url="https://example.com",
                source_engine=["querit"],
                published_date="2025-06-15",
            ),
        ]
        deduped = dedup(results)
        self.assertEqual(deduped[0].published_date, "2025-06-15")

    def test_keeps_non_null_published_date(self):
        dedup = self._get()
        results = [
            _make_result(
                url="https://example.com",
                source_engine=["exa"],
                published_date=None,
            ),
            _make_result(
                url="https://example.com",
                source_engine=["querit"],
                published_date="2025-03-01",
            ),
        ]
        deduped = dedup(results)
        self.assertEqual(deduped[0].published_date, "2025-03-01")

    def test_takes_max_score(self):
        dedup = self._get()
        results = [
            _make_result(url="https://example.com", source_engine=["exa"], score=0.3),
            _make_result(url="https://example.com", source_engine=["querit"], score=0.8),
        ]
        deduped = dedup(results)
        self.assertAlmostEqual(deduped[0].score, 0.8)

    def test_empty_list_returns_empty(self):
        dedup = self._get()
        self.assertEqual(dedup([]), [])

    def test_triple_duplicate(self):
        dedup = self._get()
        results = [
            _make_result(url="https://example.com", source_engine=["exa"]),
            _make_result(url="https://example.com", source_engine=["querit"]),
            _make_result(url="https://example.com", source_engine=["brave"]),
        ]
        deduped = dedup(results)
        self.assertEqual(len(deduped), 1)
        self.assertEqual(sorted(deduped[0].source_engine), ["brave", "exa", "querit"])


# ---------------------------------------------------------------------------
# calculate_score
# ---------------------------------------------------------------------------
class TestCalculateScore(unittest.TestCase):
    """Test cross-validation scoring with configurable weights."""

    # Default weights matching config.json values for consistent testing
    _DEFAULT_WEIGHTS = {
        "exa": 100,
        "querit": 75,
        "tavily": 70,
        "metaso": 60,
        "aliyun_iqs": 40,
        "brave": 30,
        "duckduckgo": 20,
        "bocha": 50,
    }

    def _get(self):
        funcs = _get_merger()
        return funcs[2]  # calculate_score

    def _make_with_score(self, source_engine, published_date=None, freshness=None, engine_weights=None):
        result = _make_result(source_engine=source_engine, published_date=published_date)
        from merger import calculate_score
        weights = engine_weights if engine_weights is not None else self._DEFAULT_WEIGHTS
        return calculate_score(result, freshness=freshness, engine_weights=weights)

    def test_single_engine_base_score(self):
        """Single engine: base_score = 1 * 0.3 = 0.3, plus weight bonus."""
        score = self._make_with_score(["duckduckgo"])
        # duckduckgo weight = 20, bonus = 20 * 0.002 = 0.04
        expected = 0.3 + 0.04  # = 0.34
        self.assertAlmostEqual(score, expected, places=4)

    def test_two_engines_base_score(self):
        score = self._make_with_score(["duckduckgo", "brave"])
        # base = 2*0.3=0.6, highest weight = brave=30, bonus = 30*0.002=0.06
        expected = 0.6 + 0.06  # = 0.66
        self.assertAlmostEqual(score, expected, places=4)

    def test_three_engines_base_score(self):
        score = self._make_with_score(["duckduckgo", "brave", "metaso"])
        # base = 3*0.3=0.9, highest weight = metaso=60, bonus = 60*0.002=0.12
        expected = 0.9 + 0.12  # = 1.02, clamped to 1.0
        self.assertAlmostEqual(score, 1.0, places=4)

    def test_exa_priority_bonus(self):
        score = self._make_with_score(["exa"])
        # base = 0.3, exa weight = 100, bonus = 100*0.002 = 0.20
        expected = 0.3 + 0.20  # = 0.5
        self.assertAlmostEqual(score, expected, places=4)

    def test_querit_priority_bonus(self):
        score = self._make_with_score(["querit"])
        # base = 0.3, querit weight = 75, bonus = 75*0.002 = 0.15
        expected = 0.3 + 0.15  # = 0.45
        self.assertAlmostEqual(score, expected, places=4)

    def test_metaso_priority_bonus(self):
        score = self._make_with_score(["metaso"])
        # base = 0.3, metaso weight = 60, bonus = 60*0.002 = 0.12
        expected = 0.3 + 0.12  # = 0.42
        self.assertAlmostEqual(score, expected, places=4)

    def test_aliyun_iqs_priority_bonus(self):
        score = self._make_with_score(["aliyun_iqs"])
        # base = 0.3, aliyun_iqs weight = 40, bonus = 40*0.002 = 0.08
        expected = 0.3 + 0.08  # = 0.38
        self.assertAlmostEqual(score, expected, places=4)

    def test_brave_priority_bonus(self):
        score = self._make_with_score(["brave"])
        # base = 0.3, brave weight = 30, bonus = 30*0.002 = 0.06
        expected = 0.3 + 0.06  # = 0.36
        self.assertAlmostEqual(score, expected, places=4)

    def test_duckduckgo_priority_bonus(self):
        score = self._make_with_score(["duckduckgo"])
        # base = 0.3, duckduckgo weight = 20, bonus = 20*0.002 = 0.04
        expected = 0.3 + 0.04  # = 0.34
        self.assertAlmostEqual(score, expected, places=4)

    def test_unknown_engine_no_weight_in_map(self):
        """Unknown engine uses default weight of 50 => bonus = 0.10."""
        score = self._make_with_score(["unknown_engine"])
        # base = 0.3, default weight = 50, bonus = 50*0.002 = 0.10
        expected = 0.3 + 0.10  # = 0.40
        self.assertAlmostEqual(score, expected, places=4)

    def test_no_weights_uses_default(self):
        """When engine_weights is None/empty, default weight 50 is used."""
        score = self._make_with_score(["any_engine"], engine_weights={})
        # base = 0.3, default weight = 50, bonus = 50*0.002 = 0.10
        expected = 0.3 + 0.10
        self.assertAlmostEqual(score, expected, places=4)

    def test_custom_weight_overrides_default(self):
        """Custom weight should override default values."""
        custom_weights = {"exa": 30, "myengine": 90}
        score = self._make_with_score(["exa"], engine_weights=custom_weights)
        # base = 0.3, exa weight = 30, bonus = 30*0.002 = 0.06
        expected = 0.3 + 0.06  # = 0.36
        self.assertAlmostEqual(score, expected, places=4)

    def test_weight_zero_means_no_bonus(self):
        """Weight 0 should result in no priority bonus."""
        score = self._make_with_score(["exa"], engine_weights={"exa": 0})
        expected = 0.3  # base only
        self.assertAlmostEqual(score, expected, places=4)

    def test_highest_priority_used_when_multiple(self):
        """When multiple engines, use the highest weight among them."""
        score = self._make_with_score(["duckduckgo", "exa"])
        # base = 2*0.3=0.6, highest = exa=100, bonus = 100*0.002=0.20
        expected = 0.6 + 0.20  # = 0.80
        self.assertAlmostEqual(score, expected, places=4)

    def test_recency_bonus_applied(self):
        """Recency bonus of 0.1 when published_date is within freshness window."""
        recent = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
        score = self._make_with_score(["duckduckgo"], published_date=recent, freshness="7d")
        # base = 0.3, weight = 20, bonus = 0.04, recency = 0.1
        expected = 0.3 + 0.04 + 0.1  # = 0.44
        self.assertAlmostEqual(score, expected, places=4)

    def test_recency_bonus_not_applied_when_old(self):
        """No recency bonus when published_date is outside freshness window."""
        old = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")
        score = self._make_with_score(["duckduckgo"], published_date=old, freshness="7d")
        # base = 0.3, weight = 20, bonus = 0.04, no recency
        expected = 0.3 + 0.04  # = 0.34
        self.assertAlmostEqual(score, expected, places=4)

    def test_recency_bonus_not_applied_without_freshness(self):
        """No recency bonus when freshness is None."""
        recent = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
        score = self._make_with_score(["duckduckgo"], published_date=recent, freshness=None)
        # base = 0.3, weight = 20, bonus = 0.04, no recency (no freshness specified)
        expected = 0.3 + 0.04  # = 0.34
        self.assertAlmostEqual(score, expected, places=4)

    def test_recency_bonus_not_applied_without_published_date(self):
        """No recency bonus when published_date is None."""
        score = self._make_with_score(["duckduckgo"], published_date=None, freshness="7d")
        # base = 0.3, weight = 20, bonus = 0.04, no recency (no date)
        expected = 0.3 + 0.04  # = 0.34
        self.assertAlmostEqual(score, expected, places=4)

    def test_score_clamped_to_max_one(self):
        """Score should never exceed 1.0."""
        score = self._make_with_score(["exa", "querit", "metaso"], freshness="7d")
        # base = 3*0.3=0.9, highest weight = exa=100, bonus=0.20, recency = 0.1 => 1.2, clamped to 1.0
        self.assertAlmostEqual(score, 1.0, places=4)

    def test_score_clamped_to_min_zero(self):
        """Score should never be below 0.0."""
        result = _make_result(source_engine=[], score=0.0)
        from merger import calculate_score
        score = calculate_score(result, engine_weights=self._DEFAULT_WEIGHTS)
        # 0 engines => base=0, no priority, no recency => 0.0
        self.assertGreaterEqual(score, 0.0)

    def test_freshness_1d(self):
        """freshness='1d' should accept results from the last 1 day."""
        recent = datetime.utcnow().strftime("%Y-%m-%d")
        score = self._make_with_score(["duckduckgo"], published_date=recent, freshness="1d")
        # base = 0.3, weight = 20, bonus = 0.04, recency = 0.1
        expected = 0.3 + 0.04 + 0.1  # = 0.44
        self.assertAlmostEqual(score, expected, places=4)

    def test_freshness_30d(self):
        """freshness='30d' should accept results from the last 30 days."""
        recent = (datetime.utcnow() - timedelta(days=20)).strftime("%Y-%m-%d")
        score = self._make_with_score(["duckduckgo"], published_date=recent, freshness="30d")
        # base = 0.3, weight = 20, bonus = 0.04, recency = 0.1
        expected = 0.3 + 0.04 + 0.1  # = 0.44
        self.assertAlmostEqual(score, expected, places=4)


# ---------------------------------------------------------------------------
# determine_confidence
# ---------------------------------------------------------------------------
class TestDetermineConfidence(unittest.TestCase):
    """Test confidence level determination."""

    def _get(self):
        funcs = _get_merger()
        return funcs[3]  # determine_confidence

    def test_high_confidence_three_engines(self):
        determine_confidence = self._get()
        result = _make_result(source_engine=["exa", "querit", "brave"])
        self.assertEqual(determine_confidence(result), "high")

    def test_high_confidence_four_engines(self):
        determine_confidence = self._get()
        result = _make_result(source_engine=["exa", "querit", "brave", "duckduckgo"])
        self.assertEqual(determine_confidence(result), "high")

    def test_medium_confidence_two_engines(self):
        determine_confidence = self._get()
        result = _make_result(source_engine=["exa", "querit"])
        self.assertEqual(determine_confidence(result), "medium")

    def test_low_confidence_single_engine(self):
        determine_confidence = self._get()
        result = _make_result(source_engine=["exa"])
        self.assertEqual(determine_confidence(result), "low")

    def test_low_confidence_empty_engines(self):
        determine_confidence = self._get()
        result = _make_result(source_engine=[])
        self.assertEqual(determine_confidence(result), "low")


# ---------------------------------------------------------------------------
# merge_results
# ---------------------------------------------------------------------------
class TestMergeResults(unittest.TestCase):
    """Test the main merge_results function."""

    _DEFAULT_WEIGHTS = {
        "exa": 100, "querit": 75, "tavily": 70, "metaso": 60,
        "aliyun_iqs": 40, "brave": 30, "duckduckgo": 20, "bocha": 50,
    }

    def _get(self):
        funcs = _get_merger()
        return funcs[4]  # merge_results

    def test_basic_merge(self):
        merge_results = self._get()
        engine_results = {
            "exa": [
                _make_result(title="Exa Result", url="https://example.com/a", snippet="From exa", source_engine=["exa"]),
            ],
            "querit": [
                _make_result(title="Querit Result", url="https://example.com/b", snippet="From querit", source_engine=["querit"]),
            ],
        }
        merged = merge_results(engine_results, engine_weights=self._DEFAULT_WEIGHTS)
        self.assertEqual(merged["total_results"], 2)
        self.assertEqual(len(merged["results"]), 2)
        self.assertIn("exa", merged["engines_used"])
        self.assertIn("querit", merged["engines_used"])
        self.assertEqual(merged["engines_failed"], [])
        self.assertIn("timestamp", merged)
        self.assertEqual(merged["query"], "")

    def test_deduplication_in_merge(self):
        merge_results = self._get()
        engine_results = {
            "exa": [
                _make_result(title="Result A", url="https://example.com/x", snippet="Short", source_engine=["exa"]),
            ],
            "querit": [
                _make_result(title="Result A Longer", url="https://example.com/x", snippet="Longer snippet here", source_engine=["querit"]),
            ],
        }
        merged = merge_results(engine_results, engine_weights=self._DEFAULT_WEIGHTS)
        self.assertEqual(merged["total_results"], 1)
        r = merged["results"][0]
        self.assertEqual(r.title, "Result A Longer")
        self.assertEqual(r.snippet, "Longer snippet here")
        self.assertIn("exa", r.source_engine)
        self.assertIn("querit", r.source_engine)

    def test_sorted_by_score_descending(self):
        merge_results = self._get()
        engine_results = {
            "exa": [
                _make_result(title="Single", url="https://example.com/a", snippet="A", source_engine=["exa"]),
            ],
            "brave": [
                _make_result(title="Cross", url="https://example.com/b", snippet="B", source_engine=["brave"]),
            ],
            "querit": [
                _make_result(title="Cross Too", url="https://example.com/b", snippet="B", source_engine=["querit"]),
            ],
        }
        merged = merge_results(engine_results, engine_weights=self._DEFAULT_WEIGHTS)
        # The cross-validated result (b) should have 2 engines => higher score
        self.assertEqual(merged["results"][0].url, "https://example.com/b")

    def test_engines_failed_tracking(self):
        merge_results = self._get()
        engine_results = {
            "exa": [
                _make_result(title="R", url="https://example.com/a", snippet="S", source_engine=["exa"]),
            ],
            "brave": None,  # failed
        }
        merged = merge_results(engine_results, engine_weights=self._DEFAULT_WEIGHTS)
        self.assertIn("brave", merged["engines_failed"])
        self.assertNotIn("brave", merged["engines_used"])

    def test_engines_failed_empty_list(self):
        merge_results = self._get()
        engine_results = {
            "exa": [],
            "brave": None,
        }
        merged = merge_results(engine_results, engine_weights=self._DEFAULT_WEIGHTS)
        self.assertIn("exa", merged["engines_used"])
        self.assertIn("brave", merged["engines_failed"])

    def test_overall_confidence_high(self):
        merge_results = self._get()
        # 5 results, each confirmed by 3+ engines
        engine_results = {}
        for i in range(5):
            engine_results[f"url_{i}"] = [
                _make_result(
                    title=f"Result {i}",
                    url=f"https://example.com/{i}",
                    snippet=f"Snippet {i}",
                    source_engine=["exa", "querit", "brave"],
                ),
            ]
        merged = merge_results(engine_results, engine_weights=self._DEFAULT_WEIGHTS)
        self.assertEqual(merged["overall_confidence"], "high")

    def test_overall_confidence_low(self):
        merge_results = self._get()
        engine_results = {
            "exa": [
                _make_result(title=f"R{i}", url=f"https://example.com/{i}", snippet="S", source_engine=["exa"])
                for i in range(5)
            ],
        }
        merged = merge_results(engine_results, engine_weights=self._DEFAULT_WEIGHTS)
        self.assertEqual(merged["overall_confidence"], "low")

    def test_overall_confidence_medium(self):
        merge_results = self._get()
        # top-5: first 3 have 2 engines, last 2 have 1 engine
        engine_results = {
            "exa": [
                _make_result(title=f"R{i}", url=f"https://example.com/{i}", snippet="S", source_engine=["exa"])
                for i in range(5)
            ],
            "querit": [
                _make_result(title=f"R{i}", url=f"https://example.com/{i}", snippet="S", source_engine=["querit"])
                for i in range(3)
            ],
        }
        merged = merge_results(engine_results, engine_weights=self._DEFAULT_WEIGHTS)
        # Top-5 includes 2 single-engine results => lowest confidence is "low"
        self.assertEqual(merged["overall_confidence"], "low")

    def test_overall_confidence_fewer_than_5_results(self):
        """When fewer than 5 results, use the minimum confidence of all results."""
        merge_results = self._get()
        engine_results = {
            "exa": [
                _make_result(title="R0", url="https://example.com/0", snippet="S", source_engine=["exa", "querit"]),
            ],
        }
        merged = merge_results(engine_results, engine_weights=self._DEFAULT_WEIGHTS)
        # Only 1 result with 2 engines => medium
        self.assertEqual(merged["overall_confidence"], "medium")

    def test_empty_input(self):
        merge_results = self._get()
        merged = merge_results({}, engine_weights=self._DEFAULT_WEIGHTS)
        self.assertEqual(merged["total_results"], 0)
        self.assertEqual(merged["results"], [])
        self.assertEqual(merged["engines_used"], [])
        self.assertEqual(merged["engines_failed"], [])

    def test_timestamp_is_iso8601(self):
        merge_results = self._get()
        merged = merge_results({"exa": []}, engine_weights=self._DEFAULT_WEIGHTS)
        # Should be parseable as ISO 8601
        parsed = datetime.fromisoformat(merged["timestamp"])
        self.assertIsInstance(parsed, datetime)

    def test_query_passed_through(self):
        merge_results = self._get()
        merged = merge_results({"exa": []}, query="test query", engine_weights=self._DEFAULT_WEIGHTS)
        self.assertEqual(merged["query"], "test query")

    def test_freshness_passed_to_scoring(self):
        merge_results = self._get()
        recent = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
        # Use separate input data for each call to avoid mutation issues.
        merged_no_freshness = merge_results(
            {
                "exa": [
                    _make_result(
                        title="Recent",
                        url="https://example.com/new",
                        snippet="New result",
                        source_engine=["exa"],
                        published_date=recent,
                    ),
                ],
            },
            query="test",
            engine_weights=self._DEFAULT_WEIGHTS,
        )
        merged_with_freshness = merge_results(
            {
                "exa": [
                    _make_result(
                        title="Recent",
                        url="https://example.com/new",
                        snippet="New result",
                        source_engine=["exa"],
                        published_date=recent,
                    ),
                ],
            },
            query="test",
            freshness="7d",
            engine_weights=self._DEFAULT_WEIGHTS,
        )
        # With freshness, the recent result should get a recency bonus => higher score
        self.assertGreater(
            merged_with_freshness["results"][0].score,
            merged_no_freshness["results"][0].score,
        )

    def test_custom_weights_affect_ordering(self):
        """Higher weight engines should produce higher-scored results."""
        merge_results = self._get()
        engine_results = {
            "low_engine": [
                _make_result(title="Low", url="https://example.com/low", snippet="Low", source_engine=["low_engine"]),
            ],
            "high_engine": [
                _make_result(title="High", url="https://example.com/high", snippet="High", source_engine=["high_engine"]),
            ],
        }
        weights = {"low_engine": 10, "high_engine": 100}
        merged = merge_results(engine_results, engine_weights=weights)
        # high_engine result should come first due to higher weight
        self.assertEqual(merged["results"][0].url, "https://example.com/high")


if __name__ == "__main__":
    unittest.main()
