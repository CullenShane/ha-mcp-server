"""Tests for server entry point: load_config and create_server."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from mcp.server.fastmcp import FastMCP
import pytest

from ha_mcp.config import (
    AppConfig,
    FeatureFlags,
    InstanceConfig,
    load_config,
    load_flags,
)
from ha_mcp.server import create_server, main


def _tool_names(flags: FeatureFlags) -> set[str]:
    """Return the set of tool names registered for the given feature flags."""

    server = create_server(flags=flags)
    return {t.name for t in server._tool_manager.list_tools()}


def test_load_config_missing_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """load_config raises ValueError when no config file and HA_URL is not set."""

    monkeypatch.delenv("HA_CONFIG", raising=False)
    monkeypatch.delenv("HA_URL", raising=False)
    monkeypatch.delenv("HA_TOKEN", raising=False)
    with (
        patch("ha_mcp.config.load_dotenv"),
        patch.object(Path, "exists", return_value=False),
        pytest.raises(ValueError, match="HA_URL"),
    ):
        load_config()


def test_load_config_missing_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """load_config raises ValueError when no config file and HA_TOKEN is not set."""

    monkeypatch.delenv("HA_CONFIG", raising=False)
    monkeypatch.setenv("HA_URL", "http://ha.local:8123")
    monkeypatch.delenv("HA_TOKEN", raising=False)
    with (
        patch("ha_mcp.config.load_dotenv"),
        patch.object(Path, "exists", return_value=False),
        pytest.raises(ValueError, match="HA_TOKEN"),
    ):
        load_config()


def test_load_config_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """load_config returns a single-instance AppConfig from HA_URL + HA_TOKEN."""

    monkeypatch.delenv("HA_CONFIG", raising=False)
    monkeypatch.setenv("HA_URL", "http://ha.local:8123")
    monkeypatch.setenv("HA_TOKEN", "test-token")
    with (
        patch("ha_mcp.config.load_dotenv"),
        patch.object(Path, "exists", return_value=False),
    ):
        config = load_config()

    assert isinstance(config, AppConfig)
    assert len(config.instances) == 1
    assert config.instances[0].name == "default"
    assert config.instances[0].url == "http://ha.local:8123"
    assert config.default == "default"


def test_load_config_from_yaml_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """load_config parses a YAML file when HA_CONFIG points to it."""

    yaml_file = tmp_path / "ha-mcp.yaml"
    yaml_file.write_text(
        "instances:\n"
        "  - name: home\n"
        "    url: http://home.local:8123\n"
        "    token: tok1\n"
        "  - name: office\n"
        "    url: http://office.local:8123\n"
        "    token: tok2\n"
        "default: office\n"
    )
    monkeypatch.setenv("HA_CONFIG", str(yaml_file))

    config = load_config()

    assert len(config.instances) == 2
    assert config.instances[0] == InstanceConfig(
        name="home", url="http://home.local:8123", token="tok1"
    )
    assert config.instances[1] == InstanceConfig(
        name="office", url="http://office.local:8123", token="tok2"
    )
    assert config.default == "office"


def test_load_config_from_json_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """load_config parses a JSON file when HA_CONFIG points to it."""

    json_file = tmp_path / "ha-mcp.json"
    json_file.write_text(
        json.dumps(
            {
                "instances": [
                    {"name": "home", "url": "http://home.local:8123", "token": "tok1"}
                ]
            }
        )
    )
    monkeypatch.setenv("HA_CONFIG", str(json_file))

    config = load_config()

    assert config.instances[0].name == "home"
    assert config.default == "home"


def test_load_config_missing_file_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """load_config raises FileNotFoundError when HA_CONFIG points to a missing file."""

    monkeypatch.setenv("HA_CONFIG", "/nonexistent/ha-mcp.yaml")
    with pytest.raises(FileNotFoundError, match="Config file not found"):
        load_config()


def test_load_config_empty_instances_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """load_config raises ValueError when instances list is empty."""

    yaml_file = tmp_path / "ha-mcp.yaml"
    yaml_file.write_text("instances: []\n")
    monkeypatch.setenv("HA_CONFIG", str(yaml_file))

    with pytest.raises(ValueError, match="at least one entry"):
        load_config()


def test_create_server_readonly_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """create_server defaults to read-only: only CORE_READ tools are registered."""

    monkeypatch.setenv("HA_URL", "http://ha.local:8123")
    monkeypatch.setenv("HA_TOKEN", "test-token")
    monkeypatch.delenv("HA_READONLY", raising=False)
    monkeypatch.delenv("HA_ENABLE_RESTART", raising=False)
    monkeypatch.delenv("HA_ENABLE_HASSIO", raising=False)
    monkeypatch.delenv("HA_ENABLE_SUPERVISOR", raising=False)
    monkeypatch.delenv("HA_DEPLOYMENT", raising=False)
    server = create_server()
    assert isinstance(server, FastMCP)
    names = {t.name for t in server._tool_manager.list_tools()}
    assert len(names) == 32
    assert "get_repairs_issues" in names
    assert "get_core_version" in names
    assert "validate_config" in names
    assert "set_entity_state" not in names
    assert "call_service" not in names
    assert "get_supervisor_info" not in names
    assert "restart_core" not in names
    assert "restart_ha" not in names


def test_create_server_readwrite_no_supervisor() -> None:
    """HA_READONLY=false exposes Core write tools, restarts stay gated."""

    names = _tool_names(FeatureFlags(readonly=False))
    assert len(names) == 57
    assert "set_entity_state" in names
    assert "call_service" in names
    assert "fire_event" in names
    assert "reload_config_entry" in names
    assert "create_dashboard" in names
    assert "send_notification" in names
    assert "restart_core" not in names
    assert "restart_ha" not in names
    assert "get_supervisor_info" not in names


def test_create_server_supervisor_reads_only() -> None:
    """HA_ENABLE_HASSIO with read-only registers supervisor reads, no writes."""

    names = _tool_names(FeatureFlags(readonly=True, enable_hassio=True))
    assert len(names) == 45
    assert "get_supervisor_info" in names
    assert "list_backups" in names
    assert "list_addons" in names
    assert "get_supervisor_logs" in names
    assert "update_core" not in names
    assert "create_backup" not in names
    assert "install_addon" not in names
    assert "restart_core" not in names


def test_create_server_all_enabled() -> None:
    """All flags on registers the full upstream surface plus the new fork tools."""

    names = _tool_names(
        FeatureFlags(readonly=False, enable_restart=True, enable_hassio=True)
    )
    assert len(names) == 84
    assert "restart_core" in names
    assert "restart_ha" in names
    assert "get_supervisor_info" in names
    assert "update_core" in names
    assert "install_addon" in names
    assert "get_repairs_issues" in names
    assert "restart_core" in names


def test_main_calls_run_stdio(monkeypatch: pytest.MonkeyPatch) -> None:
    """main() defaults to stdio transport when TRANSPORT is not set."""

    monkeypatch.delenv("TRANSPORT", raising=False)
    mock_server = MagicMock()
    with patch("ha_mcp.server.create_server", return_value=mock_server):
        main()
    mock_server.run.assert_called_once_with(transport="stdio")


def test_main_calls_run_sse(monkeypatch: pytest.MonkeyPatch) -> None:
    """main() uses SSE transport and correct port when TRANSPORT=sse."""

    monkeypatch.setenv("TRANSPORT", "sse")
    monkeypatch.setenv("PORT", "9000")
    mock_server = MagicMock()
    with patch("ha_mcp.server.create_server", return_value=mock_server) as mock_create:
        main()
    mock_create.assert_called_once_with(port=9000)
    mock_server.run.assert_called_once_with(transport="sse")


def test_main_rejects_invalid_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    main() raises ValueError for a TRANSPORT value outside the allowed set
    rather than silently defaulting to stdio.
    """

    monkeypatch.setenv("TRANSPORT", "bogus")
    with pytest.raises(ValueError, match="Invalid TRANSPORT"):
        main()


def test_load_flags_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """load_flags defaults to read-only with restart and hassio disabled."""

    monkeypatch.delenv("HA_READONLY", raising=False)
    monkeypatch.delenv("HA_ENABLE_RESTART", raising=False)
    monkeypatch.delenv("HA_ENABLE_HASSIO", raising=False)
    monkeypatch.delenv("HA_ENABLE_SUPERVISOR", raising=False)
    monkeypatch.delenv("HA_DEPLOYMENT", raising=False)
    flags = load_flags()
    assert flags == FeatureFlags(
        readonly=True,
        enable_restart=False,
        enable_hassio=False,
    )


@pytest.mark.parametrize("value", ["false", "0", "no", "off", "OFF"])
def test_load_flags_readonly_falsy(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    """HA_READONLY with a falsy token disables read-only (enables writes)."""

    monkeypatch.setenv("HA_READONLY", value)
    assert load_flags().readonly is False


@pytest.mark.parametrize("value", ["true", "1", "yes", "on", "TRUE"])
def test_load_flags_restart_truthy(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    """HA_ENABLE_RESTART with a truthy token enables the restart tools."""

    monkeypatch.setenv("HA_ENABLE_RESTART", value)
    assert load_flags().enable_restart is True


def test_load_flags_hassio_truthy(monkeypatch: pytest.MonkeyPatch) -> None:
    """HA_ENABLE_HASSIO with a truthy token enables the Supervisor tools."""

    monkeypatch.setenv("HA_ENABLE_HASSIO", "yes")
    assert load_flags().enable_hassio is True


def test_load_flags_deployment_container_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HA_DEPLOYMENT unset defaults to container, leaving hassio disabled."""

    monkeypatch.delenv("HA_ENABLE_HASSIO", raising=False)
    monkeypatch.delenv("HA_ENABLE_SUPERVISOR", raising=False)
    monkeypatch.delenv("HA_DEPLOYMENT", raising=False)
    assert load_flags().enable_hassio is False


def test_load_flags_deployment_supervisor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HA_DEPLOYMENT=supervised enables hassio by default."""

    monkeypatch.delenv("HA_ENABLE_HASSIO", raising=False)
    monkeypatch.delenv("HA_ENABLE_SUPERVISOR", raising=False)
    monkeypatch.setenv("HA_DEPLOYMENT", "supervised")
    assert load_flags().enable_hassio is True


def test_load_flags_hassio_override_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HA_ENABLE_HASSIO=false overrides a supervisor deployment's default."""

    monkeypatch.setenv("HA_DEPLOYMENT", "supervised")
    monkeypatch.setenv("HA_ENABLE_HASSIO", "false")
    assert load_flags().enable_hassio is False
