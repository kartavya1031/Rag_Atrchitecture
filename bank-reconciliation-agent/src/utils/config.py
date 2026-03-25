"""Configuration loader utility."""

import os
from functools import lru_cache
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

_BASE_DIR = Path(__file__).resolve().parent.parent.parent
_CONFIG_DIR = _BASE_DIR / "config"


def load_yaml(filename: str) -> dict:
    """Load a YAML config file from the config/ directory."""
    path = _CONFIG_DIR / filename
    with open(path, "r") as f:
        return yaml.safe_load(f)


@lru_cache(maxsize=1)
def get_thresholds() -> dict:
    return load_yaml("thresholds.yaml")


@lru_cache(maxsize=1)
def get_bank_rules() -> dict:
    return load_yaml("bank_rules.yaml")


def get_env(key: str, default: str | None = None) -> str | None:
    return os.getenv(key, default)
