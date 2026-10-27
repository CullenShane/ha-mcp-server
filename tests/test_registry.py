"""Tests for device and config-entry registry tools."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from unittest.mock import MagicMock

import pytest

from ha_mcp.client import HomeAssistantError
from ha_mcp.tools import registry
from tests.conftest import ToolCapture

_DEVICES: list[dict[str, Any]] = [
    {
        "id": "abc123",
        "name": "Hue Bridge",
        "manufacturer": "Philips",
        "model": "BSB002",
        "area_id": "living_room",
        "config_entries": ["entry1"],
    }
]

_CONFIG_ENTRIES: list[dict[str, Any]] = [
    {"entry_id": "entry1", "domain": "hue", "title": "Philips Hue", "state": "loaded"},
    {"entry_id": "entry2", "domain": "cast", "title": "Google Cast", "state": "loaded"},
]


@pytest.fixture
def tools() -> dict[str, Any]:
    """Register registry tools and return the tool dict."""

    capture = ToolCapture()
    registry.register(capture)  # type: ignore[arg-type]
    return capture.tools


async def test_get_device_registry_list_response(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """
    get_device_registry returns the device list when the API responds with a
    plain list.
    """

    mock_client.ws_command.return_value = _DEVICES
    result = await tools["get_device_registry"](ctx=mock_ctx)
    assert result == _DEVICES
    mock_client.ws_command.assert_called_once_with("config/device_registry/list")


async def test_list_config_entries(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """
    list_config_entries returns all config entries from
    /api/config/config_entries/entry.
    """

    mock_client.get.return_value = _CONFIG_ENTRIES
    result = await tools["list_config_entries"](ctx=mock_ctx)
    assert len(result) == 2
    assert result[0]["domain"] == "hue"
    mock_client.get.assert_called_once_with("/api/config/config_entries/entry")


async def test_reload_config_entry(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """
    reload_config_entry POSTs to the reload endpoint and returns the response
    dict.
    """

    mock_client.post.return_value = {"require_restart": False}
    result = await tools["reload_config_entry"](ctx=mock_ctx, entry_id="entry1")
    assert result == {"require_restart": False}
    mock_client.post.assert_called_once_with(
        "/api/config/config_entries/entry/entry1/reload"
    )


async def test_get_device_registry_error(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """get_device_registry propagates HomeAssistantError when the API call fails."""

    mock_client.ws_command.side_effect = HomeAssistantError("api failure")
    with pytest.raises(HomeAssistantError, match="api failure"):
        await tools["get_device_registry"](ctx=mock_ctx)


async def test_list_config_entries_error(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """list_config_entries propagates HomeAssistantError when the API call fails."""

    mock_client.get.side_effect = HomeAssistantError("api failure")
    with pytest.raises(HomeAssistantError, match="api failure"):
        await tools["list_config_entries"](ctx=mock_ctx)


async def test_reload_config_entry_error(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """reload_config_entry propagates HomeAssistantError when the API call fails."""

    mock_client.post.side_effect = HomeAssistantError("api failure")
    with pytest.raises(HomeAssistantError, match="api failure"):
        await tools["reload_config_entry"](ctx=mock_ctx, entry_id="entry1")
