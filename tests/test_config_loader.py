import json
import os
import sys
import tempfile
import unittest

# Ensure the parent directory is on sys.path so we can import config_loader
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config_loader import load_config, validate_config, get_engine_config, get_enabled_engines


class TestLoadConfig(unittest.TestCase):
    """Tests for load_config()."""

    def test_load_existing_config(self):
        """load_config should successfully load an existing config.json."""
        config_path = os.path.join(os.path.dirname(__file__), "..", "config.json")
        config = load_config(config_path)
        self.assertIsInstance(config, dict)
        self.assertEqual(config["default_engines"], ["exa", "querit", "metaso", "brave", "duckduckgo"])
        self.assertEqual(config["min_engines"], 2)
        self.assertEqual(config["timeout_seconds"], 10)
        self.assertIn("engines", config)

    def test_load_nonexistent_file_raises_FileNotFoundError(self):
        """load_config should raise FileNotFoundError when file does not exist."""
        with self.assertRaises(FileNotFoundError):
            load_config("/nonexistent/path/config.json")

    def test_load_with_default_path(self):
        """load_config with no arguments should load config.json from the same directory."""
        config = load_config()
        self.assertIsInstance(config, dict)
        self.assertIn("default_engines", config)
        self.assertIn("engines", config)


class TestValidateConfig(unittest.TestCase):
    """Tests for validate_config()."""

    def test_validate_valid_config_returns_true(self):
        """validate_config should return True for a valid config."""
        config = {
            "default_engines": ["exa", "brave"],
            "min_engines": 2,
            "timeout_seconds": 10,
            "engines": {
                "exa": {"enabled": True},
                "brave": {"enabled": True},
            },
        }
        self.assertTrue(validate_config(config))

    def test_validate_missing_default_engines_returns_false(self):
        """validate_config should return False when default_engines is missing."""
        config = {
            "min_engines": 2,
            "timeout_seconds": 10,
            "engines": {"exa": {"enabled": True}},
        }
        self.assertFalse(validate_config(config))

    def test_validate_missing_engines_returns_false(self):
        """validate_config should return False when engines is missing."""
        config = {
            "default_engines": ["exa"],
            "min_engines": 2,
            "timeout_seconds": 10,
        }
        self.assertFalse(validate_config(config))

    def test_validate_min_engines_less_than_one_returns_false(self):
        """validate_config should return False when min_engines < 1."""
        config = {
            "default_engines": ["exa"],
            "min_engines": 0,
            "timeout_seconds": 10,
            "engines": {"exa": {"enabled": True}},
        }
        self.assertFalse(validate_config(config))

    def test_validate_min_engines_negative_returns_false(self):
        """validate_config should return False when min_engines is negative."""
        config = {
            "default_engines": ["exa"],
            "min_engines": -1,
            "timeout_seconds": 10,
            "engines": {"exa": {"enabled": True}},
        }
        self.assertFalse(validate_config(config))

    def test_validate_timeout_seconds_zero_returns_false(self):
        """validate_config should return False when timeout_seconds <= 0."""
        config = {
            "default_engines": ["exa"],
            "min_engines": 1,
            "timeout_seconds": 0,
            "engines": {"exa": {"enabled": True}},
        }
        self.assertFalse(validate_config(config))

    def test_validate_timeout_seconds_negative_returns_false(self):
        """validate_config should return False when timeout_seconds is negative."""
        config = {
            "default_engines": ["exa"],
            "min_engines": 1,
            "timeout_seconds": -5,
            "engines": {"exa": {"enabled": True}},
        }
        self.assertFalse(validate_config(config))


class TestGetEngineConfig(unittest.TestCase):
    """Tests for get_engine_config()."""

    def test_get_existing_engine_returns_config(self):
        """get_engine_config should return the engine's config dict."""
        config = {
            "engines": {
                "exa": {"api_key": "test-key", "type": "auto", "enabled": True},
                "brave": {"api_key": "brave-key", "enabled": True},
            }
        }
        result = get_engine_config(config, "exa")
        self.assertEqual(result, {"api_key": "test-key", "type": "auto", "enabled": True})

    def test_get_nonexistent_engine_returns_empty_dict(self):
        """get_engine_config should return an empty dict for unknown engines."""
        config = {
            "engines": {
                "exa": {"enabled": True},
            }
        }
        result = get_engine_config(config, "nonexistent")
        self.assertEqual(result, {})

    def test_get_engine_config_missing_engines_key(self):
        """get_engine_config should return empty dict when config has no 'engines' key."""
        config = {}
        result = get_engine_config(config, "exa")
        self.assertEqual(result, {})


class TestGetEnabledEngines(unittest.TestCase):
    """Tests for get_enabled_engines()."""

    def test_returns_all_enabled_engines(self):
        """get_enabled_engines should return names of all engines with enabled=True."""
        config = {
            "engines": {
                "exa": {"enabled": True},
                "brave": {"enabled": True},
                "duckduckgo": {"enabled": True},
            }
        }
        result = get_enabled_engines(config)
        self.assertIn("exa", result)
        self.assertIn("brave", result)
        self.assertIn("duckduckgo", result)
        self.assertEqual(len(result), 3)

    def test_skips_disabled_engines(self):
        """get_enabled_engines should skip engines with enabled=False."""
        config = {
            "engines": {
                "exa": {"enabled": True},
                "brave": {"enabled": False},
                "duckduckgo": {"enabled": True},
                "aliyun_iqs": {"enabled": False},
            }
        }
        result = get_enabled_engines(config)
        self.assertIn("exa", result)
        self.assertIn("duckduckgo", result)
        self.assertNotIn("brave", result)
        self.assertNotIn("aliyun_iqs", result)
        self.assertEqual(len(result), 2)

    def test_engines_without_enabled_key_are_skipped(self):
        """get_enabled_engines should skip engines that don't have 'enabled' key."""
        config = {
            "engines": {
                "exa": {"enabled": True},
                "weird": {"api_key": "abc"},
            }
        }
        result = get_enabled_engines(config)
        self.assertEqual(result, ["exa"])

    def test_returns_empty_list_when_no_engines(self):
        """get_enabled_engines should return empty list when engines dict is empty."""
        config = {"engines": {}}
        result = get_enabled_engines(config)
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
