"""
Configuration loader for unified-search.

Loads, validates, and provides access to search engine configurations
defined in config.json.
"""

import json
import os
from pathlib import Path


_DEFAULT_CONFIG_DIR = Path(__file__).resolve().parent
_DEFAULT_CONFIG_PATH = _DEFAULT_CONFIG_DIR / "config.json"


def load_config(config_path=None):
    """Load and return the configuration from a JSON file.

    Args:
        config_path: Path to the config file. Defaults to config.json
                     in the same directory as this module.

    Returns:
        dict: The parsed configuration.

    Raises:
        FileNotFoundError: If the config file does not exist.
        json.JSONDecodeError: If the config file contains invalid JSON.
    """
    if config_path is None:
        config_path = str(_DEFAULT_CONFIG_PATH)

    if not os.path.isfile(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_config(config):
    """Validate a configuration dictionary.

    Checks that required fields exist and values are within acceptable ranges.

    Args:
        config: dict to validate.

    Returns:
        bool: True if the configuration is valid, False otherwise.
    """
    # Required top-level keys
    if "default_engines" not in config:
        return False
    if "engines" not in config:
        return False

    # min_engines must be >= 1 (if present)
    min_engines = config.get("min_engines", 1)
    if not isinstance(min_engines, (int, float)) or min_engines < 1:
        return False

    # timeout_seconds must be > 0 (if present)
    timeout_seconds = config.get("timeout_seconds", 10)
    if not isinstance(timeout_seconds, (int, float)) or timeout_seconds <= 0:
        return False

    return True


def get_engine_config(config, engine_name):
    """Get the configuration for a specific search engine.

    Args:
        config: The full configuration dict.
        engine_name: Name of the engine to look up.

    Returns:
        dict: The engine's configuration, or an empty dict if not found.
    """
    engines = config.get("engines", {})
    if not isinstance(engines, dict):
        return {}
    return engines.get(engine_name, {})


def get_enabled_engines(config):
    """Return a list of engine names that have enabled=True.

    Engines without an 'enabled' key are skipped.

    Args:
        config: The full configuration dict.

    Returns:
        list: Names of all enabled engines.
    """
    engines = config.get("engines", {})
    if not isinstance(engines, dict):
        return []

    return [
        name
        for name, engine_conf in engines.items()
        if isinstance(engine_conf, dict) and engine_conf.get("enabled") is True
    ]


def get_engine_weights(config):
    """Return a dict mapping engine name to its weight (int).

    Weight range: 1-100. Higher weight = higher priority in result scoring.
    Engines without a 'weight' key default to 50.

    Args:
        config: The full configuration dict.

    Returns:
        dict: {engine_name: weight_int, ...}
    """
    engines = config.get("engines", {})
    if not isinstance(engines, dict):
        return {}

    weights = {}
    for name, engine_conf in engines.items():
        if not isinstance(engine_conf, dict):
            continue
        w = engine_conf.get("weight", 50)
        if not isinstance(w, (int, float)) or w < 0:
            w = 50
        weights[name] = int(w)
    return weights
