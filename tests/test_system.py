"""Tests for system information and configuration tools."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from unittest.mock import MagicMock

import pytest

from ha_mcp.client import HomeAssistantError
from ha_mcp.tools import system
from tests.conftest import ToolCapture

_HA_CONFIG: dict[str, Any] = {
    "version": "2024.1.0",
    "location_name": "Home",
    "latitude": 52.37,
    "longitude": 4.89,
    "unit_system": {"length": "km"},
    "time_zone": "Europe/Amsterdam",
    "components": ["sensor", "light"],
}

_SUPERVISOR_DATA: dict[str, Any] = {
    "version": "2024.01.0",
    "version_latest": "2024.01.0",
    "channel": "stable",
    "update_available": False,
}

_USERS: list[dict[str, Any]] = [
    {"id": "abc123", "name": "Admin", "is_active": True, "is_admin": True},
    {"id": "def456", "name": "User", "is_active": True, "is_admin": False},
]

_BACKUPS: list[dict[str, Any]] = [
    {
        "slug": "abc123",
        "name": "Full Backup",
        "date": "2024-01-01T00:00:00",
        "size": 123456,
        "type": "full",
    }
]


@pytest.fixture
def tools() -> dict[str, Any]:
    """Register system tools and return the tool dict."""

    capture = ToolCapture()
    system.register(capture)  # type: ignore[arg-type]
    return capture.tools


async def test_get_ha_config(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """get_ha_config returns the HA configuration dict from /api/config."""

    mock_client.get.return_value = _HA_CONFIG
    result = await tools["get_ha_config"](ctx=mock_ctx)
    assert result["version"] == "2024.1.0"
    mock_client.get.assert_called_once_with("/api/config")


async def test_check_config_valid(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """
    check_config returns the validation result dict when the configuration is
    valid.
    """

    mock_client.post.return_value = {"result": "valid", "errors": []}
    result = await tools["check_config"](ctx=mock_ctx)
    assert result["result"] == "valid"
    mock_client.post.assert_called_once_with("/api/config/core/check_config")


async def test_check_config_invalid(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """
    check_config returns the validation result dict including errors when
    config is invalid.
    """

    mock_client.post.return_value = {
        "result": "invalid",
        "errors": ["Unknown key: invalid_key"],
    }
    result = await tools["check_config"](ctx=mock_ctx)
    assert result["result"] == "invalid"
    assert len(result["errors"]) == 1


async def test_restart_ha(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """
    restart_ha POSTs to the core restart endpoint and returns a confirmation
    string.
    """

    mock_client.post.return_value = "restarting"
    result = await tools["restart_ha"](ctx=mock_ctx)
    assert "restarting" in result
    mock_client.post.assert_called_once_with("/api/config/core/restart")


async def test_get_supervisor_info(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """
    get_supervisor_info returns the supervisor data dict from the nested
    data key.
    """

    mock_client.get.return_value = {"data": _SUPERVISOR_DATA}
    result = await tools["get_supervisor_info"](ctx=mock_ctx)
    assert result == _SUPERVISOR_DATA
    mock_client.get.assert_called_once_with("/api/hassio/supervisor/info")


async def test_get_supervisor_info_fallback(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """Falls back to full response when no 'data' key."""

    mock_client.get.return_value = _SUPERVISOR_DATA
    result = await tools["get_supervisor_info"](ctx=mock_ctx)
    assert result == _SUPERVISOR_DATA


async def test_get_core_info(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """get_core_info returns the core data dict from the nested data key."""

    mock_client.get.return_value = {"data": _SUPERVISOR_DATA}
    result = await tools["get_core_info"](ctx=mock_ctx)
    assert result == _SUPERVISOR_DATA
    mock_client.get.assert_called_once_with("/api/hassio/core/info")


async def test_get_host_info(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """get_host_info returns the host data dict from the nested data key."""

    mock_client.get.return_value = {"data": {"hostname": "homeassistant"}}
    result = await tools["get_host_info"](ctx=mock_ctx)
    assert result["hostname"] == "homeassistant"
    mock_client.get.assert_called_once_with("/api/hassio/host/info")


async def test_get_os_info(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """get_os_info returns the OS data dict from the nested data key."""

    mock_client.get.return_value = {
        "data": {"version": "11.0", "version_latest": "11.0"}
    }
    result = await tools["get_os_info"](ctx=mock_ctx)
    assert result["version"] == "11.0"
    mock_client.get.assert_called_once_with("/api/hassio/os/info")


async def test_update_core(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """
    update_core POSTs to the core update endpoint and returns the result
    string.
    """

    mock_client.post.return_value = {"result": "ok"}
    result = await tools["update_core"](ctx=mock_ctx)
    assert result == "ok"
    mock_client.post.assert_called_once_with("/api/hassio/core/update")


async def test_update_supervisor(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """
    update_supervisor POSTs to the supervisor update endpoint and returns
    the result string.
    """

    mock_client.post.return_value = {"result": "ok"}
    result = await tools["update_supervisor"](ctx=mock_ctx)
    assert result == "ok"
    mock_client.post.assert_called_once_with("/api/hassio/supervisor/update")


async def test_update_os(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """
    update_os POSTs to the OS update endpoint and returns the result
    string.
    """

    mock_client.post.return_value = {"result": "ok"}
    result = await tools["update_os"](ctx=mock_ctx)
    assert result == "ok"
    mock_client.post.assert_called_once_with("/api/hassio/os/update")


async def test_list_integrations(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """
    list_integrations returns all config entries from
    /api/config/config_entries/entry.
    """

    entries = [{"entry_id": "e1", "domain": "hue", "title": "Hue", "state": "loaded"}]
    mock_client.get.return_value = entries
    result = await tools["list_integrations"](ctx=mock_ctx)
    assert len(result) == 1
    mock_client.get.assert_called_once_with("/api/config/config_entries/entry")


async def test_get_system_health(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """
    get_system_health returns the system health dict from
    /api/system_health.
    """

    health = {"homeassistant": {"info": {"version": "2024.1.0"}}}
    mock_client.ws_command.return_value = health
    result = await tools["get_system_health"](ctx=mock_ctx)
    assert "homeassistant" in result
    mock_client.ws_command.assert_called_once_with("system_health/info")


async def test_list_users(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """
    list_users returns all user records from /api/config/auth/users.
    """

    mock_client.get.return_value = _USERS
    result = await tools["list_users"](ctx=mock_ctx)
    assert len(result) == 2
    assert result[0]["is_admin"] is True
    mock_client.get.assert_called_once_with("/api/config/auth/users")


async def test_create_backup(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """
    create_backup POSTs to the full backup endpoint and returns the backup data
    dict.
    """

    mock_client.post.return_value = {"data": {"slug": "abc123"}}
    result = await tools["create_backup"](ctx=mock_ctx)
    assert result["slug"] == "abc123"
    mock_client.post.assert_called_once_with("/api/hassio/backups/new/full")


async def test_create_backup_fallback(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """Falls back to full response when no 'data' key."""

    mock_client.post.return_value = {"slug": "abc123"}
    result = await tools["create_backup"](ctx=mock_ctx)
    assert result["slug"] == "abc123"


async def test_list_backups(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """
    list_backups returns the backup list from the nested data.backups key.
    """

    mock_client.get.return_value = {"data": {"backups": _BACKUPS}}
    result = await tools["list_backups"](ctx=mock_ctx)
    assert result == _BACKUPS
    mock_client.get.assert_called_once_with("/api/hassio/backups")


async def test_list_backups_empty(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """list_backups returns an empty list when no backups exist."""

    mock_client.get.return_value = {"data": {"backups": []}}
    result = await tools["list_backups"](ctx=mock_ctx)
    assert result == []


async def test_get_ha_config_error(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """get_ha_config propagates HomeAssistantError on API failure."""

    mock_client.get.side_effect = HomeAssistantError("api failure")
    with pytest.raises(HomeAssistantError, match="api failure"):
        await tools["get_ha_config"](ctx=mock_ctx)


async def test_check_config_error(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """check_config propagates HomeAssistantError on API failure."""

    mock_client.post.side_effect = HomeAssistantError("api failure")
    with pytest.raises(HomeAssistantError, match="api failure"):
        await tools["check_config"](ctx=mock_ctx)


async def test_restart_ha_error(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """restart_ha propagates HomeAssistantError on API failure."""

    mock_client.post.side_effect = HomeAssistantError("api failure")
    with pytest.raises(HomeAssistantError, match="api failure"):
        await tools["restart_ha"](ctx=mock_ctx)


async def test_get_supervisor_info_error(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """get_supervisor_info propagates HomeAssistantError on API failure."""

    mock_client.get.side_effect = HomeAssistantError("api failure")
    with pytest.raises(HomeAssistantError, match="api failure"):
        await tools["get_supervisor_info"](ctx=mock_ctx)


async def test_get_core_info_error(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """get_core_info propagates HomeAssistantError on API failure."""

    mock_client.get.side_effect = HomeAssistantError("api failure")
    with pytest.raises(HomeAssistantError, match="api failure"):
        await tools["get_core_info"](ctx=mock_ctx)


async def test_get_host_info_error(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """get_host_info propagates HomeAssistantError on API failure."""

    mock_client.get.side_effect = HomeAssistantError("api failure")
    with pytest.raises(HomeAssistantError, match="api failure"):
        await tools["get_host_info"](ctx=mock_ctx)


async def test_get_os_info_error(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """get_os_info propagates HomeAssistantError on API failure."""

    mock_client.get.side_effect = HomeAssistantError("api failure")
    with pytest.raises(HomeAssistantError, match="api failure"):
        await tools["get_os_info"](ctx=mock_ctx)


async def test_update_core_error(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """update_core propagates HomeAssistantError on API failure."""

    mock_client.post.side_effect = HomeAssistantError("api failure")
    with pytest.raises(HomeAssistantError, match="api failure"):
        await tools["update_core"](ctx=mock_ctx)


async def test_update_supervisor_error(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """update_supervisor propagates HomeAssistantError on API failure."""

    mock_client.post.side_effect = HomeAssistantError("api failure")
    with pytest.raises(HomeAssistantError, match="api failure"):
        await tools["update_supervisor"](ctx=mock_ctx)


async def test_update_os_error(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """update_os propagates HomeAssistantError on API failure."""

    mock_client.post.side_effect = HomeAssistantError("api failure")
    with pytest.raises(HomeAssistantError, match="api failure"):
        await tools["update_os"](ctx=mock_ctx)


async def test_list_integrations_error(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """list_integrations propagates HomeAssistantError on API failure."""

    mock_client.get.side_effect = HomeAssistantError("api failure")
    with pytest.raises(HomeAssistantError, match="api failure"):
        await tools["list_integrations"](ctx=mock_ctx)


async def test_get_system_health_null(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """get_system_health returns None when there are no issues."""

    mock_client.ws_command.return_value = None
    result = await tools["get_system_health"](ctx=mock_ctx)
    assert result is None


async def test_get_system_health_error(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """get_system_health propagates HomeAssistantError on API failure."""

    mock_client.ws_command.side_effect = HomeAssistantError("api failure")
    with pytest.raises(HomeAssistantError, match="api failure"):
        await tools["get_system_health"](ctx=mock_ctx)


async def test_list_users_error(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """list_users propagates HomeAssistantError on API failure."""

    mock_client.get.side_effect = HomeAssistantError("api failure")
    with pytest.raises(HomeAssistantError, match="api failure"):
        await tools["list_users"](ctx=mock_ctx)


async def test_create_backup_error(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """create_backup propagates HomeAssistantError on API failure."""

    mock_client.post.side_effect = HomeAssistantError("api failure")
    with pytest.raises(HomeAssistantError, match="api failure"):
        await tools["create_backup"](ctx=mock_ctx)


async def test_list_backups_error(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """list_backups propagates HomeAssistantError on API failure."""

    mock_client.get.side_effect = HomeAssistantError("api failure")
    with pytest.raises(HomeAssistantError, match="api failure"):
        await tools["list_backups"](ctx=mock_ctx)
