"""Tests for TOML config loading in uhcr/cli.py (_load_config)."""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from uhcr.cli import _load_config


class TestLoadConfig:
    """Tests for _load_config helper function."""

    def test_explicit_config_path_loads_all_keys(self, tmp_path):
        """All supported keys under [server] are loaded correctly."""
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            '[server]\n'
            'host = "127.0.0.1"\n'
            'grpc_port = 9090\n'
            'http_port = 8081\n'
            'workers = 8\n'
            'grace_period = 60\n'
            'redis_url = "redis://localhost:6379/0"\n'
            'sqlite_path = "/var/lib/uhcr/data.db"\n'
        )

        result = _load_config(str(config_file))

        assert result["host"] == "127.0.0.1"
        assert result["grpc_port"] == 9090
        assert result["http_port"] == 8081
        assert result["workers"] == 8
        assert result["grace_period"] == 60
        assert result["redis_url"] == "redis://localhost:6379/0"
        assert result["sqlite_path"] == "/var/lib/uhcr/data.db"

    def test_explicit_config_path_partial_keys(self, tmp_path):
        """Only specified keys are returned; missing keys are omitted."""
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            '[server]\n'
            'host = "10.0.0.1"\n'
            'workers = 16\n'
        )

        result = _load_config(str(config_file))

        assert result == {"host": "10.0.0.1", "workers": 16}
        assert "grpc_port" not in result
        assert "http_port" not in result
        assert "grace_period" not in result
        assert "redis_url" not in result
        assert "sqlite_path" not in result

    def test_explicit_config_path_not_found_raises(self, tmp_path):
        """FileNotFoundError raised when explicit path doesn't exist."""
        with pytest.raises(FileNotFoundError, match="Config file not found"):
            _load_config(str(tmp_path / "nonexistent.toml"))

    def test_no_config_path_no_default_returns_empty(self, tmp_path):
        """Returns empty dict when no explicit path and default doesn't exist."""
        # Patch Path.home() to a temp dir without .uhcr/config.toml
        with patch.object(Path, "home", return_value=tmp_path):
            result = _load_config(None)

        assert result == {}

    def test_no_config_path_loads_default_location(self, tmp_path):
        """Loads from ~/.uhcr/config.toml when no explicit path given."""
        uhcr_dir = tmp_path / ".uhcr"
        uhcr_dir.mkdir()
        config_file = uhcr_dir / "config.toml"
        config_file.write_text(
            '[server]\n'
            'host = "192.168.1.1"\n'
            'grpc_port = 5000\n'
        )

        with patch.object(Path, "home", return_value=tmp_path):
            result = _load_config(None)

        assert result["host"] == "192.168.1.1"
        assert result["grpc_port"] == 5000

    def test_top_level_keys_used_when_no_server_section(self, tmp_path):
        """Keys at top level are used if [server] section is absent."""
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            'host = "0.0.0.0"\n'
            'grpc_port = 50051\n'
            'http_port = 8080\n'
        )

        result = _load_config(str(config_file))

        assert result["host"] == "0.0.0.0"
        assert result["grpc_port"] == 50051
        assert result["http_port"] == 8080

    def test_integer_values_coerced(self, tmp_path):
        """Integer keys are coerced to int even if TOML stores them as int."""
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            '[server]\n'
            'grpc_port = 12345\n'
            'http_port = 54321\n'
            'workers = 2\n'
            'grace_period = 10\n'
        )

        result = _load_config(str(config_file))

        assert isinstance(result["grpc_port"], int)
        assert isinstance(result["http_port"], int)
        assert isinstance(result["workers"], int)
        assert isinstance(result["grace_period"], int)

    def test_empty_server_section_returns_empty(self, tmp_path):
        """Empty [server] section returns empty dict."""
        config_file = tmp_path / "config.toml"
        config_file.write_text('[server]\n')

        result = _load_config(str(config_file))

        assert result == {}

    def test_cli_override_logic(self, tmp_path):
        """Verify that CLI flags override config file values (integration-style)."""
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            '[server]\n'
            'host = "10.0.0.1"\n'
            'grpc_port = 9090\n'
            'http_port = 9091\n'
            'workers = 8\n'
            'grace_period = 45\n'
        )

        config = _load_config(str(config_file))

        # Simulate CLI override logic from _cmd_serve
        cli_host = "127.0.0.1"  # explicitly set
        cli_grpc_port = None     # not set
        cli_http_port = 7070     # explicitly set
        cli_workers = None       # not set
        cli_grace_period = None  # not set

        host = cli_host if cli_host is not None else config.get("host", "0.0.0.0")
        grpc_port = cli_grpc_port if cli_grpc_port is not None else config.get("grpc_port", 50051)
        http_port = cli_http_port if cli_http_port is not None else config.get("http_port", 8080)
        workers = cli_workers if cli_workers is not None else config.get("workers", 4)
        grace_period = cli_grace_period if cli_grace_period is not None else config.get("grace_period", 30)

        # CLI values win
        assert host == "127.0.0.1"
        assert http_port == 7070
        # Config values used when CLI is None
        assert grpc_port == 9090
        assert workers == 8
        assert grace_period == 45
