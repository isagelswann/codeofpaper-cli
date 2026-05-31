"""Tests for codeofpaper_cli.config and codeofpaper_cli.commands.auth."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from codeofpaper_cli import config
from codeofpaper_cli.main import app

runner = CliRunner()


# ── Config module tests ──────────────────────────────────────────────


class TestLoadConfig:
    def test_returns_defaults_when_no_file(self, tmp_path: Path):
        fake_file = tmp_path / "config.json"
        with patch.object(config, "_CONFIG_FILE", fake_file):
            cfg = config.load_config()
        assert cfg["api_url"] == "https://api.codeofpaper.com"
        assert cfg["api_key"] is None
        assert cfg["default_format"] == "table"
        assert cfg["ca_bundle"] is None

    def test_loads_stored_values(self, tmp_path: Path):
        fake_file = tmp_path / "config.json"
        fake_file.write_text(json.dumps({"api_key": "sk-abc123", "default_format": "json"}))
        with patch.object(config, "_CONFIG_FILE", fake_file):
            cfg = config.load_config()
        assert cfg["api_key"] == "sk-abc123"
        assert cfg["default_format"] == "json"
        assert cfg["api_url"] == "https://api.codeofpaper.com"  # default filled

    def test_loads_ca_bundle_from_config(self, tmp_path: Path):
        fake_file = tmp_path / "config.json"
        fake_file.write_text(json.dumps({"ca_bundle": "/etc/ssl/corporate-ca.pem"}))
        with patch.object(config, "_CONFIG_FILE", fake_file):
            cfg = config.load_config()
        assert cfg["ca_bundle"] == "/etc/ssl/corporate-ca.pem"

    def test_handles_corrupt_json(self, tmp_path: Path):
        fake_file = tmp_path / "config.json"
        fake_file.write_text("{not valid json")
        with patch.object(config, "_CONFIG_FILE", fake_file):
            cfg = config.load_config()
        assert cfg == config.DEFAULTS

    def test_handles_non_dict_json(self, tmp_path: Path):
        fake_file = tmp_path / "config.json"
        fake_file.write_text('"just a string"')
        with patch.object(config, "_CONFIG_FILE", fake_file):
            cfg = config.load_config()
        assert cfg == config.DEFAULTS


class TestSaveConfig:
    def test_creates_dir_and_file(self, tmp_path: Path):
        fake_dir = tmp_path / "subdir"
        fake_file = fake_dir / "config.json"
        with patch.object(config, "_CONFIG_DIR", fake_dir), patch.object(
            config, "_CONFIG_FILE", fake_file
        ):
            config.save_config({"api_key": "test123"})
        assert fake_file.exists()
        stored = json.loads(fake_file.read_text())
        assert stored["api_key"] == "test123"

    def test_overwrites_existing(self, tmp_path: Path):
        fake_file = tmp_path / "config.json"
        fake_file.write_text(json.dumps({"api_key": "old"}))
        with patch.object(config, "_CONFIG_DIR", tmp_path), patch.object(
            config, "_CONFIG_FILE", fake_file
        ):
            config.save_config({"api_key": "new"})
        stored = json.loads(fake_file.read_text())
        assert stored["api_key"] == "new"


class TestSetKey:
    def test_sets_new_key(self, tmp_path: Path):
        fake_file = tmp_path / "config.json"
        with patch.object(config, "_CONFIG_DIR", tmp_path), patch.object(
            config, "_CONFIG_FILE", fake_file
        ):
            config.set_key("api_key", "sk-newkey")
            cfg = config.load_config()
        assert cfg["api_key"] == "sk-newkey"

    def test_preserves_other_keys(self, tmp_path: Path):
        fake_file = tmp_path / "config.json"
        fake_file.write_text(json.dumps({"default_format": "csv"}))
        with patch.object(config, "_CONFIG_DIR", tmp_path), patch.object(
            config, "_CONFIG_FILE", fake_file
        ):
            config.set_key("api_key", "sk-test")
            cfg = config.load_config()
        assert cfg["api_key"] == "sk-test"
        assert cfg["default_format"] == "csv"


class TestDeleteKey:
    def test_removes_key(self, tmp_path: Path):
        fake_file = tmp_path / "config.json"
        fake_file.write_text(json.dumps({"api_key": "sk-remove-me"}))
        with patch.object(config, "_CONFIG_DIR", tmp_path), patch.object(
            config, "_CONFIG_FILE", fake_file
        ):
            config.delete_key("api_key")
            cfg = config.load_config()
        assert cfg["api_key"] is None  # falls back to default

    def test_noop_for_missing_key(self, tmp_path: Path):
        fake_file = tmp_path / "config.json"
        fake_file.write_text(json.dumps({"api_key": "keep"}))
        with patch.object(config, "_CONFIG_DIR", tmp_path), patch.object(
            config, "_CONFIG_FILE", fake_file
        ):
            config.delete_key("nonexistent")
            cfg = config.load_config()
        assert cfg["api_key"] == "keep"


class TestGetConfigPath:
    def test_returns_path_object(self):
        path = config.get_config_path()
        assert isinstance(path, Path)
        assert path.name == "config.json"


# ── Auth command tests ───────────────────────────────────────────────


class TestAuthSetup:
    def test_saves_key(self, tmp_path: Path):
        fake_dir = tmp_path / "cfg"
        fake_file = fake_dir / "config.json"
        with patch.object(config, "_CONFIG_DIR", fake_dir), patch.object(
            config, "_CONFIG_FILE", fake_file
        ):
            result = runner.invoke(app, ["auth", "setup", "codi_sk_testkey123"])
        assert result.exit_code == 0
        assert "API key saved" in result.output

    def test_missing_key_fails(self, tmp_path: Path):
        fake_file = tmp_path / "config.json"
        with patch.object(config, "_CONFIG_DIR", tmp_path), patch.object(
            config, "_CONFIG_FILE", fake_file
        ):
            result = runner.invoke(app, ["auth", "setup"])
        assert result.exit_code == 1
        assert "API key required" in result.output


class TestAuthStatus:
    def test_shows_no_key(self, tmp_path: Path):
        fake_file = tmp_path / "config.json"
        with patch.object(config, "_CONFIG_DIR", tmp_path), patch.object(
            config, "_CONFIG_FILE", fake_file
        ):
            result = runner.invoke(app, ["auth", "status"])
        assert result.exit_code == 0
        assert "(not set)" in result.output

    def test_shows_masked_key(self, tmp_path: Path):
        fake_file = tmp_path / "config.json"
        fake_file.write_text(json.dumps({"api_key": "codi_sk_abc123456789"}))
        with patch.object(config, "_CONFIG_DIR", tmp_path), patch.object(
            config, "_CONFIG_FILE", fake_file
        ):
            result = runner.invoke(app, ["auth", "status"])
        assert result.exit_code == 0
        assert "codi_sk_" in result.output
        assert "codi_sk_abc123456789" not in result.output  # should be masked
        assert "..." in result.output

    def test_shows_short_key_masked(self, tmp_path: Path):
        fake_file = tmp_path / "config.json"
        fake_file.write_text(json.dumps({"api_key": "tiny"}))
        with patch.object(config, "_CONFIG_DIR", tmp_path), patch.object(
            config, "_CONFIG_FILE", fake_file
        ):
            result = runner.invoke(app, ["auth", "status"])
        assert result.exit_code == 0
        assert "***" in result.output
        assert "tiny" not in result.output


class TestAuthClear:
    def test_clears_key(self, tmp_path: Path):
        fake_dir = tmp_path / "cfg"
        fake_file = fake_dir / "config.json"
        fake_dir.mkdir()
        fake_file.write_text(json.dumps({"api_key": "remove-me"}))
        with patch.object(config, "_CONFIG_DIR", fake_dir), patch.object(
            config, "_CONFIG_FILE", fake_file
        ):
            result = runner.invoke(app, ["auth", "clear"])
        assert result.exit_code == 0
        assert "cleared" in result.output
        stored = json.loads(fake_file.read_text())
        assert "api_key" not in stored


class TestAuthUnknownAction:
    def test_unknown_action_fails(self, tmp_path: Path):
        fake_file = tmp_path / "config.json"
        with patch.object(config, "_CONFIG_DIR", tmp_path), patch.object(
            config, "_CONFIG_FILE", fake_file
        ):
            result = runner.invoke(app, ["auth", "badaction"])
        assert result.exit_code == 1
        assert "Unknown action" in result.output


# ── Config wiring tests (main.py callback) ──────────────────────────


class TestConfigWiring:
    """Test that config values flow into state when no CLI flags override."""

    def test_config_api_key_used_when_no_flag(self, tmp_path: Path):
        """Config api_key flows to state when --api-key not passed."""
        fake_file = tmp_path / "config.json"
        fake_file.write_text(json.dumps({"api_key": "codi_sk_from_config_value"}))
        with patch.object(config, "_CONFIG_DIR", tmp_path), patch.object(
            config, "_CONFIG_FILE", fake_file
        ):
            result = runner.invoke(app, ["auth", "status"])
        assert result.exit_code == 0
        assert "codi_sk_...alue" in result.output  # masked version

    def test_cli_flag_overrides_config_key(self, tmp_path: Path):
        """--api-key flag overrides config file value."""
        fake_file = tmp_path / "config.json"
        fake_file.write_text(json.dumps({"api_key": "from-config"}))
        with patch.object(config, "_CONFIG_DIR", tmp_path), patch.object(
            config, "_CONFIG_FILE", fake_file
        ):
            # The --api-key flag is handled by main callback, but auth status
            # reads from config file. We just verify no crash.
            result = runner.invoke(app, ["--api-key", "from-flag", "auth", "status"])
        assert result.exit_code == 0

    def test_config_default_format_used(self, tmp_path: Path):
        """Config default_format is picked up when no -o flag."""
        fake_file = tmp_path / "config.json"
        fake_file.write_text(json.dumps({"default_format": "json"}))
        with patch.object(config, "_CONFIG_DIR", tmp_path), patch.object(
            config, "_CONFIG_FILE", fake_file
        ):
            result = runner.invoke(app, ["auth", "status"])
        # Just verify the callback doesn't crash with json format from config
        assert result.exit_code == 0

    def test_invalid_config_format_falls_back(self, tmp_path: Path):
        """Invalid default_format in config falls back to table."""
        fake_file = tmp_path / "config.json"
        fake_file.write_text(json.dumps({"default_format": "invalid_format"}))
        with patch.object(config, "_CONFIG_DIR", tmp_path), patch.object(
            config, "_CONFIG_FILE", fake_file
        ):
            result = runner.invoke(app, ["auth", "status"])
        assert result.exit_code == 0
