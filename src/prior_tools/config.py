"""Configuration management for Prior SDK. Stores config at ~/.prior/config.json."""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

CONFIG_DIR = Path.home() / ".prior"
CONFIG_FILE = CONFIG_DIR / "config.json"

_DEFAULTS = {
    "base_url": "https://share.cg3.io",
    "api_key": None,
    "agent_id": None,
}


def load_config() -> Dict[str, Any]:
    """Load config from ~/.prior/config.json, falling back to env vars and defaults."""
    config = dict(_DEFAULTS)

    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                config.update(json.load(f))
        except (json.JSONDecodeError, OSError):
            pass

    # Env vars override file config
    if val := os.environ.get("PRIOR_BASE_URL"):
        config["base_url"] = val
    if val := os.environ.get("PRIOR_API_KEY"):
        config["api_key"] = val
    if val := os.environ.get("PRIOR_AGENT_ID"):
        config["agent_id"] = val

    return config


def save_config(config: Dict[str, Any]) -> None:
    """Save config to ~/.prior/config.json."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def get_config_value(key: str) -> Optional[Any]:
    """Get a single config value."""
    return load_config().get(key)
