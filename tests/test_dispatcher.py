"""Tests for dispatcher.py — get_available_engines, search_parallel, main()."""

import io
import json
import os
import sys
import time
import unittest
from unittest.mock import MagicMock, patch, PropertyMock

# ---------------------------------------------------------------------------
# Ensure the project root is on sys.path so imports work from the test dir.
# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


# ---------------------------------------------------------------------------
# Helper: build a lightweight fake engine
# ---------------------------------------------------------------------------

def _make_fake_engine(
    name="fake",
    display_name="Fake Engine",
    priority=100,
    requires_key=False,
    available=True,
    results=None,
    search_side_effect=None,
):
    """Return a MagicMock that quacks like a BaseEngine."""
    engine = MagicMock()
    engine.name = name
    engine.display_name = display_name
    engine.priority = priority
    engine.requires_key = requires_key
    engine.is_available.return_value = available
    if search_side_effect is not None:
        engine.search.side_effect = search_side_effect
    elif results is not None:
        engine.search.return_value = results
    else:
        engine.search.return_value = []
    return engine


def _make_search_result(title="Title", url="https://example.com", snippet="Snippet", source_engine=None, **kwargs):
    """Build a SearchResult dataclass instance."""
    from engines.base import SearchResult
    return SearchResult(
        title=title,
        url=url,
        snippet=snippet,
        source_engine=source_engine or ["fake"],
        **kwargs,
    )


# ===========================================================================
# get_available_engines
# ===========================================================================


class TestGetAvailableEngines(unittest.TestCase):
    """Test get_available_engines dynamic discovery and filtering."""

    def test_returns_available_engines(self):
        """Only engines where is_available returns True are included."""
        from dispatcher import get_available_engines

        engine_a = _make_fake_engine(name="alpha", available=True)
        engine_b = _make_fake_engine(name="beta", available=False)
        engine_c = _make_fake_engine(name="gamma", available=True)

        engines_list = [engine_a, engine_b, engine_c]
        config = {
            "engines": {
                "alpha": {"enabled": True},
                "beta": {"enabled": True},
                "gamma": {"enabled": True},
            }
        }

        with patch("dispatcher._discover_engine_classes", return_value=[]), \
             patch("dispatcher._instantiate_engines", return_value=engines_list):
            result = get_available_engines(config)

        names = [e.name for e in result]
        self.assertIn("alpha", names)
        self.assertNotIn("beta", names)
        self.assertIn("gamma", names)

    def test_filters_by_enabled_engines_in_config(self):
        """Only engines listed in config as enabled should be checked."""
        from dispatcher import get_available_engines

        engine_a = _make_fake_engine(name="alpha", available=True)
        engine_b = _make_fake_engine(name="beta", available=True)

        engines_list = [engine_a, engine_b]
        # beta is NOT in config, so it should not appear
        config = {
            "engines": {
                "alpha": {"enabled": True},
            }
        }

        with patch("dispatcher._discover_engine_classes", return_value=[]), \
             patch("dispatcher._instantiate_engines", return_value=engines_list):
            result = get_available_engines(config)

        names = [e.name for e in result]
        self.assertIn("alpha", names)
        self.assertNotIn("beta", names)

    def test_empty_config_returns_empty_list(self):
        """An empty config should yield no available engines."""
        from dispatcher import get_available_engines

        with patch("dispatcher._discover_engine_classes", return_value=[]), \
             patch("dispatcher._instantiate_engines", return_value=[]):
            result = get_available_engines({})

        self.assertEqual(result, [])

    def test_returns_list_of_base_engine_instances(self):
        """Result items should have name attribute (duck-typing BaseEngine)."""
        from dispatcher import get_available_engines

        engine = _make_fake_engine(name="test_engine", available=True)
        config = {"engines": {"test_engine": {"enabled": True}}}

        with patch("dispatcher._discover_engine_classes", return_value=[]), \
             patch("dispatcher._instantiate_engines", return_value=[engine]):
            result = get_available_engines(config)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "test_engine")


# ===========================================================================
# search_parallel
# ===========================================================================


class TestSearchParallel(unittest.TestCase):
    """Test search_parallel concurrent execution and error handling."""

    def test_all_engines_succeed(self):
        """When all engines succeed, results dict contains all engine names."""
        from dispatcher import search_parallel

        r1 = [_make_search_result(title="R1", source_engine=["a"])]
        r2 = [_make_search_result(title="R2", source_engine=["b"])]
        engine_a = _make_fake_engine(name="a", results=r1)
        engine_b = _make_fake_engine(name="b", results=r2)

        config = {"engines": {"a": {}, "b": {}}}
        result = search_parallel("test query", [engine_a, engine_b], config)

        self.assertIn("a", result["results"])
        self.assertIn("b", result["results"])
        self.assertEqual(result["results"]["a"], r1)
        self.assertEqual(result["results"]["b"], r2)
        self.assertEqual(result["failed"], [])

    def test_single_engine_failure(self):
        """One engine raising an exception should not affect the other."""
        from dispatcher import search_parallel

        r1 = [_make_search_result(title="R1", source_engine=["a"])]
        engine_a = _make_fake_engine(name="a", results=r1)
        engine_b = _make_fake_engine(name="b", search_side_effect=RuntimeError("boom"))

        config = {"engines": {"a": {}, "b": {}}}
        result = search_parallel("test", [engine_a, engine_b], config)

        self.assertIn("a", result["results"])
        self.assertNotIn("b", result["results"])
        self.assertIn("b", result["failed"])

    def test_timeout_causes_engine_failure(self):
        """An engine that takes too long should be recorded as failed."""
        from dispatcher import search_parallel

        def slow_search(*args, **kwargs):
            time.sleep(10)
            return []

        engine_slow = _make_fake_engine(name="slow", search_side_effect=slow_search)
        config = {"engines": {"slow": {}}}
        result = search_parallel("test", [engine_slow], config, timeout=1)

        self.assertIn("slow", result["failed"])

    def test_empty_engine_list(self):
        """No engines should yield empty results and no failures."""
        from dispatcher import search_parallel

        result = search_parallel("test", [], {})
        self.assertEqual(result["results"], {})
        self.assertEqual(result["failed"], [])

    def test_engine_called_with_config(self):
        """Each engine should receive its own config via keyword arg."""
        from dispatcher import search_parallel

        engine_a = _make_fake_engine(name="a")
        config = {"engines": {"a": {"api_key": "secret"}}}
        search_parallel("test", [engine_a], config)

        engine_a.search.assert_called_once()
        call_kwargs = engine_a.search.call_args
        # config should be passed as keyword argument
        self.assertEqual(call_kwargs.kwargs.get("config"), {"api_key": "secret"})

    def test_max_results_forwarded(self):
        """max_results parameter should be forwarded to engine.search."""
        from dispatcher import search_parallel

        engine = _make_fake_engine(name="a")
        config = {"engines": {"a": {}}}
        search_parallel("test", [engine], config, max_results=5)

        call_kwargs = engine.search.call_args
        self.assertEqual(call_kwargs.kwargs.get("max_results"), 5)

    def test_freshness_forwarded(self):
        """freshness parameter should be forwarded to engine.search."""
        from dispatcher import search_parallel

        engine = _make_fake_engine(name="a")
        config = {"engines": {"a": {}}}
        search_parallel("test", [engine], config, freshness="pw")

        call_kwargs = engine.search.call_args
        self.assertEqual(call_kwargs.kwargs.get("freshness"), "pw")


# ===========================================================================
# main() CLI
# ===========================================================================


class TestMainCLI(unittest.TestCase):
    """Test main() argument parsing, output format, and exit codes."""

    def test_basic_query_output(self):
        """main() with a valid query prints JSON to stdout."""
        from dispatcher import main

        engine_a = _make_fake_engine(
            name="a",
            results=[_make_search_result(title="Hello A", source_engine=["a"])],
        )
        engine_b = _make_fake_engine(
            name="b",
            results=[_make_search_result(title="Hello B", source_engine=["b"])],
        )

        config = {
            "default_engines": ["a", "b"],
            "min_engines": 2,
            "engines": {"a": {"enabled": True}, "b": {"enabled": True}},
        }

        with patch("dispatcher.load_config", return_value=config), \
             patch("dispatcher.get_available_engines", return_value=[engine_a, engine_b]), \
             patch("sys.argv", ["dispatcher.py", "test query"]):
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                exit_code = main()

        output = mock_out.getvalue()
        self.assertEqual(exit_code, 0)
        parsed = json.loads(output)
        self.assertIn("query", parsed)
        self.assertIn("results", parsed)

    def test_compact_mode_omits_snippet_and_date(self):
        """--compact should strip snippet and published_date from results."""
        from dispatcher import main

        engine = _make_fake_engine(
            name="a",
            results=[
                _make_search_result(
                    title="Hello",
                    snippet="A long snippet here",
                    published_date="2025-01-01",
                    source_engine=["a"],
                )
            ],
        )

        config = {
            "default_engines": ["a"],
            "min_engines": 1,
            "engines": {"a": {"enabled": True}},
        }

        with patch("dispatcher.load_config", return_value=config), \
             patch("dispatcher.get_available_engines", return_value=[engine]), \
             patch("sys.argv", ["dispatcher.py", "test", "--compact"]):
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                main()

        output = mock_out.getvalue()
        parsed = json.loads(output)
        for result in parsed.get("results", []):
            self.assertNotIn("snippet", result)
            self.assertNotIn("published_date", result)

    def test_freshness_flag(self):
        """--freshness flag should be passed to engines."""
        from dispatcher import main

        engine = _make_fake_engine(
            name="a",
            results=[_make_search_result(title="T", source_engine=["a"])],
        )

        config = {
            "default_engines": ["a"],
            "min_engines": 1,
            "engines": {"a": {"enabled": True}},
        }

        with patch("dispatcher.load_config", return_value=config), \
             patch("dispatcher.get_available_engines", return_value=[engine]), \
             patch("sys.argv", ["dispatcher.py", "test", "--freshness", "pw"]):
            with patch("sys.stdout", new_callable=io.StringIO):
                main()

        engine.search.assert_called_once()
        call_kwargs = engine.search.call_args
        self.assertEqual(call_kwargs.kwargs.get("freshness"), "pw")

    def test_engines_flag_filters(self):
        """--engines exa,querit should only use those engines."""
        from dispatcher import main

        engine_a = _make_fake_engine(
            name="a",
            results=[_make_search_result(title="T", source_engine=["a"])],
        )
        engine_b = _make_fake_engine(
            name="b",
            results=[_make_search_result(title="T", source_engine=["b"])],
        )

        config = {
            "default_engines": ["a", "b"],
            "min_engines": 1,
            "engines": {"a": {"enabled": True}, "b": {"enabled": True}},
        }

        with patch("dispatcher.load_config", return_value=config), \
             patch("dispatcher.get_available_engines", return_value=[engine_a, engine_b]), \
             patch("sys.argv", ["dispatcher.py", "test", "--engines", "a"]):
            with patch("sys.stdout", new_callable=io.StringIO):
                main()

        engine_a.search.assert_called_once()
        engine_b.search.assert_not_called()

    def test_max_results_flag(self):
        """--max-results 3 should forward max_results=3 to engines."""
        from dispatcher import main

        engine = _make_fake_engine(
            name="a",
            results=[_make_search_result(title="T", source_engine=["a"])],
        )

        config = {
            "default_engines": ["a"],
            "min_engines": 1,
            "engines": {"a": {"enabled": True}},
        }

        with patch("dispatcher.load_config", return_value=config), \
             patch("dispatcher.get_available_engines", return_value=[engine]), \
             patch("sys.argv", ["dispatcher.py", "test", "--max-results", "3"]):
            with patch("sys.stdout", new_callable=io.StringIO):
                main()

        call_kwargs = engine.search.call_args
        self.assertEqual(call_kwargs.kwargs.get("max_results"), 3)

    def test_exit_code_zero_two_engines(self):
        """Exit code 0 when 2+ engines return results."""
        from dispatcher import main

        engine_a = _make_fake_engine(
            name="a",
            results=[_make_search_result(title="T", source_engine=["a"])],
        )
        engine_b = _make_fake_engine(
            name="b",
            results=[_make_search_result(title="T", source_engine=["b"])],
        )

        config = {
            "default_engines": ["a", "b"],
            "min_engines": 2,
            "engines": {"a": {"enabled": True}, "b": {"enabled": True}},
        }

        with patch("dispatcher.load_config", return_value=config), \
             patch("dispatcher.get_available_engines", return_value=[engine_a, engine_b]), \
             patch("sys.argv", ["dispatcher.py", "test"]):
            with patch("sys.stdout", new_callable=io.StringIO):
                exit_code = main()

        self.assertEqual(exit_code, 0)

    def test_exit_code_one_partial_success(self):
        """Exit code 1 when only 1 engine returns results (below min_engines=2)."""
        from dispatcher import main

        engine_a = _make_fake_engine(
            name="a",
            results=[_make_search_result(title="T", source_engine=["a"])],
        )
        engine_b = _make_fake_engine(
            name="b",
            search_side_effect=RuntimeError("fail"),
        )

        config = {
            "default_engines": ["a", "b"],
            "min_engines": 2,
            "engines": {"a": {"enabled": True}, "b": {"enabled": True}},
        }

        with patch("dispatcher.load_config", return_value=config), \
             patch("dispatcher.get_available_engines", return_value=[engine_a, engine_b]), \
             patch("sys.argv", ["dispatcher.py", "test"]):
            with patch("sys.stdout", new_callable=io.StringIO):
                exit_code = main()

        self.assertEqual(exit_code, 1)

    def test_exit_code_two_total_failure(self):
        """Exit code 2 when no engines return results."""
        from dispatcher import main

        engine_a = _make_fake_engine(name="a", search_side_effect=RuntimeError("fail"))
        engine_b = _make_fake_engine(name="b", search_side_effect=RuntimeError("fail"))

        config = {
            "default_engines": ["a", "b"],
            "min_engines": 1,
            "engines": {"a": {"enabled": True}, "b": {"enabled": True}},
        }

        with patch("dispatcher.load_config", return_value=config), \
             patch("dispatcher.get_available_engines", return_value=[engine_a, engine_b]), \
             patch("sys.argv", ["dispatcher.py", "test"]):
            with patch("sys.stdout", new_callable=io.StringIO):
                exit_code = main()

        self.assertEqual(exit_code, 2)

    def test_no_available_engines_exit_two(self):
        """Exit code 2 when no engines are available at all."""
        from dispatcher import main

        config = {
            "default_engines": ["a"],
            "min_engines": 1,
            "engines": {"a": {"enabled": True}},
        }

        with patch("dispatcher.load_config", return_value=config), \
             patch("dispatcher.get_available_engines", return_value=[]), \
             patch("sys.argv", ["dispatcher.py", "test"]):
            with patch("sys.stdout", new_callable=io.StringIO):
                exit_code = main()

        self.assertEqual(exit_code, 2)


# ===========================================================================
# _module_name_to_class_name
# ===========================================================================


class TestModuleNameToClassName(unittest.TestCase):
    """Test the module-name-to-class-name mapping rule."""

    def test_simple_name(self):
        """exa -> ExaEngine"""
        from dispatcher import _module_name_to_class_name
        self.assertEqual(_module_name_to_class_name("exa"), "ExaEngine")

    def test_snake_case_single(self):
        """duckduckgo -> DuckduckgoEngine (single part, capitalize first)."""
        from dispatcher import _module_name_to_class_name
        self.assertEqual(_module_name_to_class_name("duckduckgo"), "DuckduckgoEngine")

    def test_snake_case_with_underscore(self):
        """aliyun_iqs -> AliyunIqsEngine"""
        from dispatcher import _module_name_to_class_name
        self.assertEqual(_module_name_to_class_name("aliyun_iqs"), "AliyunIqsEngine")


# ===========================================================================
# _discover_engine_classes
# ===========================================================================


class TestDiscoverEngineClasses(unittest.TestCase):
    """Test dynamic discovery of engine classes from engines/ directory."""

    def test_discovers_engine_classes(self):
        """Should find and return Engine classes from engines/ modules."""
        from dispatcher import _discover_engine_classes

        classes = _discover_engine_classes()
        # At minimum, DuckDuckGoEngine should be discoverable (no API key needed)
        class_names = [cls.__name__ for cls in classes]
        self.assertIn("DuckDuckGoEngine", class_names)

    def test_excludes_base_and_init(self):
        """Should not include base.py or __init__.py."""
        from dispatcher import _discover_engine_classes

        classes = _discover_engine_classes()
        class_names = [cls.__name__ for cls in classes]
        self.assertNotIn("BaseEngine", class_names)


if __name__ == "__main__":
    unittest.main()
