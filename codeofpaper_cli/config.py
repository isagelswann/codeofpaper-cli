"""Persistent config file for the CLI.

Location (via platformdirs):
    Linux:   ~/.config/codeofpaper/config.json
    macOS:   ~/Library/Application Support/codeofpaper/config.json
    Windows: %APPDATA%\\codeofpaper\\config.json

Fields:
    api_url:        API base URL (default: https://api.codeofpaper.com)
    api_key:        Stored API key (default: None)
    default_format: Default output format (default: table)

No config file = fully working CLI (anonymous, 60 req/min).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import platformdirs

_CONFIG_DIR = Path(platformdirs.user_config_dir("codeofpaper"))
_CONFIG_FILE = _CONFIG_DIR / "config.json"

DEFAULTS: dict[str, Any] = {
    "api_url": "https://api.codeofpaper.com",
    "api_key": None,
    "default_format": "table",
}


def load_config() -> dict[str, Any]:
    """Load config from disk, merged with defaults.

    Returns defaults for any missing keys. Returns all defaults if
    no config file exists.
    """
    config = dict(DEFAULTS)
    if _CONFIG_FILE.exists():
        try:
            with open(_CONFIG_FILE) as f:
                stored = json.load(f)
            if isinstance(stored, dict):
                config.update(stored)
        except (json.JSONDecodeError, OSError):
            pass  # Corrupt/unreadable file — fall back to defaults
    return config


def save_config(config: dict[str, Any]) -> None:
    """Save config dict to disk, creating directory if needed."""
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(_CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
        f.write("\n")


def get_config_path() -> Path:
    """Return the config file path (for display purposes)."""
    return _CONFIG_FILE


def set_key(key: str, value: Any) -> None:
    """Set a single config key and save."""
    config = load_config()
    config[key] = value
    save_config(config)


def delete_key(key: str) -> None:
    """Remove a key from config (reset to default) and save."""
    config = load_config()
    config.pop(key, None)
    save_config(config)
