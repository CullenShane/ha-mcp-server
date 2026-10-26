"""Tests for repairs and core tools."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from unittest.mock import MagicMock

import pytest

from ha_mcp.client import HomeAssistantError
from ha_mcp.tools import repairs
from tests.conftest import ToolCapture

_ISSUES: list[dict[str, Any]] = [
    {"issue_id": "i1", "domain": "hue", "severity": "warning"},
    {
        "issue_id": "i2",
        "domain": "mqtt",
        "severity": "error",
        "dismissed_version": "2024.1",
    },
    {
        "issue_id": "i3",
        "domain": "mqtt",
        "severity": "error",
        "dismissed_version": None,
    },
]

_CONFIG: dict[str, Any] = {"version": "2024.1.0", "location_name": "Home"}

_ENTRIES: list[dict[str, Any]] = [
    {
        "entry_id": "e1",
        "domain": "hue",
        "title": "Hue",
        "state": "loaded",
        "source": "import",
    },
    {
        "entry_id": "e2",
        "domain": "mqtt",
        "title": "MQTT",
        "state": "loaded",
        "source": "user",
    },
    {
        "entry_id": "e3",
        "domain": "hue",
        "title": "Hue",
        "state": "loaded",
        "source": "import",
    },
    {
        "entry_id": "e4",
        "domain": "mqtt",
        "title": "MQTT",
        "state": "setup_error",
        "source": "user",
    },
]

_LOG: dict[str, Any] = {
    "log_full": (
        "DEBUG: start\n"
        "INFO: info1\n"
        "WARNING: warn1\n"
        "ERROR: err1\n"
        "INFO: info2\n"
        "DEBUG: debug2\n"
        "WARNING: warn2\n"
        "ERROR: err2\n"
    ),
}


@pytest.fixture
def tools() -> dict[str, Any]:
    """Register repairs tools and return the tool dict."""

    capture = ToolCapture()
    repairs.register(capture)  # type: ignore[arg-type]
    return capture.tools


async def test_get_repairs_issues_list(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """
    get_repairs_issues returns a bare list and filters out issues with a
    non-null dismissed_version by default.
    """

    mock_client.get.return_value = _ISSUES
    result = await tools["get_repairs_issues"](ctx=mock_ctx)
    assert result == [_ISSUES[0], _ISSUES[2]]
    mock_client.get.assert_called_once_with("/api/repairs/issues")


async def test_get_repairs_issues_dict_form(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """
    get_repairs_issues normalises a dict response by reading the issues key.
    """

    mock_client.get.return_value = {"issues": _ISSUES}
    result = await tools["get_repairs_issues"](ctx=mock_ctx)
    assert result == [_ISSUES[0], _ISSUES[2]]


async def test_get_repairs_issues_include_dismissed(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """get_repairs_issues returns all issues when include_dismissed is True."""

    mock_client.get.return_value = _ISSUES
    result = await tools["get_repairs_issues"](ctx=mock_ctx, include_dismissed=True)
    assert result == _ISSUES


async def test_get_repairs_issue_detail(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """
    get_repairs_issue_detail returns the nested data dict from the issue
    registry endpoint.
    """

    mock_client.get.return_value = {"data": {"issue_id": "i1", "severity": "warning"}}
    result = await tools["get_repairs_issue_detail"](ctx=mock_ctx, issue_id="i1")
    assert result == {"issue_id": "i1", "severity": "warning"}
    mock_client.get.assert_called_once_with("/api/repairs/issue_registry/i1")


async def test_get_repairs_issue_detail_fallback(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """get_repairs_issue_detail falls back to the full response when no data key."""

    mock_client.get.return_value = {"issue_id": "i1", "severity": "warning"}
    result = await tools["get_repairs_issue_detail"](ctx=mock_ctx, issue_id="i1")
    assert result == {"issue_id": "i1", "severity": "warning"}


async def test_get_core_version(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """get_core_version returns the version key from /api/config."""

    mock_client.get.return_value = _CONFIG
    result = await tools["get_core_version"](ctx=mock_ctx)
    assert result == {"version": "2024.1.0"}
    mock_client.get.assert_called_once_with("/api/config")


async def test_list_loaded_integrations(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """
    list_loaded_integrations projects each entry to domain, title, state, and
    source, de-duplicates identical dicts, and sorts by domain then title.
    """

    mock_client.get.return_value = _ENTRIES
    result = await tools["list_loaded_integrations"](ctx=mock_ctx)
    assert len(result) == 3
    assert result[0] == {
        "domain": "hue",
        "title": "Hue",
        "state": "loaded",
        "source": "import",
    }
    assert result[1] == {
        "domain": "mqtt",
        "title": "MQTT",
        "state": "loaded",
        "source": "user",
    }
    assert result[2] == {
        "domain": "mqtt",
        "title": "MQTT",
        "state": "setup_error",
        "source": "user",
    }
    mock_client.get.assert_called_once_with("/api/config/config_entries/entry")


async def test_get_ha_log_level_filter_and_tail(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """
    get_ha_log keeps lines at or above min_level and returns the last tail
    matching lines.
    """

    mock_client.get.return_value = _LOG
    result = await tools["get_ha_log"](ctx=mock_ctx, tail=2)
    assert result == "WARNING: warn2\nERROR: err2"
    mock_client.get.assert_called_once_with("/api/log")


async def test_get_ha_log_error_level(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """get_ha_log keeps only ERROR lines when min_level is ERROR."""

    mock_client.get.return_value = _LOG
    result = await tools["get_ha_log"](ctx=mock_ctx, tail=10, min_level="ERROR")
    assert result == "ERROR: err1\nERROR: err2"


async def test_get_ha_log_debug_keeps_all(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """get_ha_log keeps all lines when min_level is DEBUG."""

    mock_client.get.return_value = _LOG
    result = await tools["get_ha_log"](ctx=mock_ctx, tail=3, min_level="DEBUG")
    assert result == "DEBUG: debug2\nWARNING: warn2\nERROR: err2"


async def test_get_ha_log_log_small_fallback(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """get_ha_log falls back to log_small when log_full is absent."""

    mock_client.get.return_value = {"log_small": "WARNING: warn1\nERROR: err1\n"}
    result = await tools["get_ha_log"](ctx=mock_ctx, tail=2)
    assert result == "WARNING: warn1\nERROR: err1"


async def test_get_ha_log_string_response(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """get_ha_log handles a plain string response."""

    mock_client.get.return_value = "WARNING: warn1\nERROR: err1\n"
    result = await tools["get_ha_log"](ctx=mock_ctx, tail=2)
    assert result == "WARNING: warn1\nERROR: err1"


async def test_validate_config(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """validate_config POSTs to /api/config/check and returns the result dict."""

    mock_client.post.return_value = {"result": "valid", "errors": []}
    result = await tools["validate_config"](ctx=mock_ctx)
    assert result == {"result": "valid", "errors": []}
    mock_client.post.assert_called_once_with("/api/config/check")


async def test_restart_core(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """restart_core POSTs to the restart service and returns a confirmation string."""

    mock_client.post.return_value = "restarting"
    result = await tools["restart_core"](ctx=mock_ctx)
    assert result == "restarting"
    mock_client.post.assert_called_once_with("/api/services/homeassistant/restart")


async def test_get_repairs_issues_error(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """get_repairs_issues propagates HomeAssistantError on API failure."""

    mock_client.get.side_effect = HomeAssistantError("api failure")
    with pytest.raises(HomeAssistantError, match="api failure"):
        await tools["get_repairs_issues"](ctx=mock_ctx)


async def test_get_repairs_issue_detail_error(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """get_repairs_issue_detail propagates HomeAssistantError on API failure."""

    mock_client.get.side_effect = HomeAssistantError("api failure")
    with pytest.raises(HomeAssistantError, match="api failure"):
        await tools["get_repairs_issue_detail"](ctx=mock_ctx, issue_id="i1")


async def test_get_core_version_error(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """get_core_version propagates HomeAssistantError on API failure."""

    mock_client.get.side_effect = HomeAssistantError("api failure")
    with pytest.raises(HomeAssistantError, match="api failure"):
        await tools["get_core_version"](ctx=mock_ctx)


async def test_list_loaded_integrations_error(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """list_loaded_integrations propagates HomeAssistantError on API failure."""

    mock_client.get.side_effect = HomeAssistantError("api failure")
    with pytest.raises(HomeAssistantError, match="api failure"):
        await tools["list_loaded_integrations"](ctx=mock_ctx)


async def test_get_ha_log_error(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """get_ha_log propagates HomeAssistantError on API failure."""

    mock_client.get.side_effect = HomeAssistantError("api failure")
    with pytest.raises(HomeAssistantError, match="api failure"):
        await tools["get_ha_log"](ctx=mock_ctx)


async def test_validate_config_error(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """validate_config propagates HomeAssistantError on API failure."""

    mock_client.post.side_effect = HomeAssistantError("api failure")
    with pytest.raises(HomeAssistantError, match="api failure"):
        await tools["validate_config"](ctx=mock_ctx)


async def test_restart_core_error(
    tools: dict[str, Any], mock_ctx: MagicMock, mock_client: MagicMock
) -> None:
    """restart_core propagates HomeAssistantError on API failure."""

    mock_client.post.side_effect = HomeAssistantError("api failure")
    with pytest.raises(HomeAssistantError, match="api failure"):
        await tools["restart_core"](ctx=mock_ctx)
