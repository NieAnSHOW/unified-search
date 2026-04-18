"""Tests for BaseEngine and SearchResult."""

import unittest
from dataclasses import fields
from typing import List


class TestSearchResult(unittest.TestCase):
    """Test SearchResult dataclass creation and default values."""

    def _get_SearchResult(self):
        """Lazily import SearchResult to allow tests to run before implementation."""
        from engines.base import SearchResult
        return SearchResult

    def test_create_with_all_fields(self):
        """SearchResult can be created with all fields specified."""
        SearchResult = self._get_SearchResult()
        result = SearchResult(
            title="Test Title",
            url="https://example.com",
            snippet="A test snippet",
            source_engine=["exa", "google"],
            published_date="2025-01-01",
            score=0.95,
        )
        self.assertEqual(result.title, "Test Title")
        self.assertEqual(result.url, "https://example.com")
        self.assertEqual(result.snippet, "A test snippet")
        self.assertEqual(result.source_engine, ["exa", "google"])
        self.assertEqual(result.published_date, "2025-01-01")
        self.assertEqual(result.score, 0.95)

    def test_default_published_date_is_none(self):
        """published_date defaults to None when not specified."""
        SearchResult = self._get_SearchResult()
        result = SearchResult(
            title="Title",
            url="https://example.com",
            snippet="Snippet",
            source_engine=["exa"],
            score=0.5,
        )
        self.assertIsNone(result.published_date)

    def test_source_engine_accepts_empty_list(self):
        """source_engine can be an empty list."""
        SearchResult = self._get_SearchResult()
        result = SearchResult(
            title="Title",
            url="https://example.com",
            snippet="Snippet",
            source_engine=[],
            score=0.5,
        )
        self.assertEqual(result.source_engine, [])

    def test_score_range_minimum(self):
        """score can be 0.0."""
        SearchResult = self._get_SearchResult()
        result = SearchResult(
            title="Title",
            url="https://example.com",
            snippet="Snippet",
            source_engine=["exa"],
            score=0.0,
        )
        self.assertEqual(result.score, 0.0)

    def test_score_range_maximum(self):
        """score can be 1.0."""
        SearchResult = self._get_SearchResult()
        result = SearchResult(
            title="Title",
            url="https://example.com",
            snippet="Snippet",
            source_engine=["exa"],
            score=1.0,
        )
        self.assertEqual(result.score, 1.0)

    def test_has_expected_fields(self):
        """SearchResult has exactly the expected fields."""
        SearchResult = self._get_SearchResult()
        field_names = {f.name for f in fields(SearchResult)}
        expected = {"title", "url", "snippet", "source_engine", "published_date", "score"}
        self.assertEqual(field_names, expected)


class TestBaseEngineCannotInstantiate(unittest.TestCase):
    """Test that BaseEngine cannot be directly instantiated."""

    def test_cannot_instantiate_base_engine(self):
        """Attempting to instantiate BaseEngine directly raises TypeError."""
        from engines.base import BaseEngine

        with self.assertRaises(TypeError):
            BaseEngine()


class TestConcreteEngineRequirements(unittest.TestCase):
    """Test that subclasses must implement abstract methods."""

    def _make_minimal_subclass(self):
        """Create a subclass that only implements _normalize."""
        from engines.base import BaseEngine, SearchResult

        class MinimalEngine(BaseEngine):
            name = "minimal"
            display_name = "Minimal Engine"
            priority = 10
            requires_key = False

            def search(self, query, max_results=10, freshness=None):
                return []

            def _normalize(self, raw_results):
                return []

        return MinimalEngine()

    def test_subclass_must_implement_search(self):
        """A subclass missing search() cannot be instantiated."""
        from engines.base import BaseEngine

        class NoSearch(BaseEngine):
            name = "no_search"
            display_name = "No Search"
            priority = 10
            requires_key = False

            def _normalize(self, raw_results):
                return []

        with self.assertRaises(TypeError):
            NoSearch()

    def test_subclass_must_implement_normalize(self):
        """A subclass missing _normalize() cannot be instantiated."""
        from engines.base import BaseEngine

        class NoNormalize(BaseEngine):
            name = "no_normalize"
            display_name = "No Normalize"
            priority = 10
            requires_key = False

            def search(self, query, max_results=10, freshness=None):
                return []

        with self.assertRaises(TypeError):
            NoNormalize()

    def test_subclass_with_all_methods_can_instantiate(self):
        """A subclass implementing all abstract methods can be instantiated."""
        engine = self._make_minimal_subclass()
        self.assertEqual(engine.name, "minimal")
        self.assertEqual(engine.display_name, "Minimal Engine")
        self.assertEqual(engine.priority, 10)
        self.assertFalse(engine.requires_key)


class TestIsAvailable(unittest.TestCase):
    """Test is_available logic."""

    def _make_engine(self, requires_key, api_key=None):
        """Create a test engine with given requires_key and optional api_key in config."""
        from engines.base import BaseEngine, SearchResult

        _requires_key = requires_key  # avoid name shadowing inside class body

        class TestEngine(BaseEngine):
            name = "test"
            display_name = "Test Engine"
            priority = 10
            requires_key = _requires_key

            def search(self, query, max_results=10, freshness=None):
                return []

            def _normalize(self, raw_results):
                return []

        config = {}
        if api_key is not None:
            config["api_key"] = api_key
        return TestEngine(), config

    def test_available_with_key_when_required(self):
        """is_available returns True when requires_key=True and key is present."""
        engine, config = self._make_engine(requires_key=True, api_key="secret-key")
        self.assertTrue(engine.is_available(config))

    def test_not_available_without_key_when_required(self):
        """is_available returns False when requires_key=True and no key in config."""
        engine, config = self._make_engine(requires_key=True)
        self.assertFalse(engine.is_available(config))

    def test_available_without_key_when_not_required(self):
        """is_available returns True when requires_key=False and no key."""
        engine, config = self._make_engine(requires_key=False)
        self.assertTrue(engine.is_available(config))

    def test_available_with_key_when_not_required(self):
        """is_available returns True when requires_key=False and key is present."""
        engine, config = self._make_engine(requires_key=False, api_key="some-key")
        self.assertTrue(engine.is_available(config))

    def test_not_available_with_empty_key_when_required(self):
        """is_available returns False when requires_key=True and key is empty string."""
        engine, config = self._make_engine(requires_key=True, api_key="")
        self.assertFalse(engine.is_available(config))

    def test_not_available_with_whitespace_key_when_required(self):
        """is_available returns False when requires_key=True and key is whitespace."""
        engine, config = self._make_engine(requires_key=True, api_key="   ")
        self.assertFalse(engine.is_available(config))


if __name__ == "__main__":
    unittest.main()
