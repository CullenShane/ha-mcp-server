"""MCP tools for Home Assistant repairs, logs, and core configuration."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ha_mcp.tools.gating import DEFAULT_FLAGS, ToolKind, make_registrar

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from ha_mcp.client import HomeAssistantClient
    from ha_mcp.config import FeatureFlags

# Core log severity ranks in ascending order. Used by get_ha_log to filter
# structured system_log/list entries.
_LEVEL_RANK: dict[str, int] = {
    "DEBUG": 0,
    "INFO": 1,
    "WARNING": 2,
    "ERROR": 3,
    "CRITICAL": 4,
}


def _level_rank(level: Any) -> int:
    """
    Return the severity rank for a log level token.

    Args:
        level: The level token (e.g. "WARNING").

    Returns:
        The severity rank (DEBUG=0 .. CRITICAL=4); unknown levels rank as 2.
    """

    return _LEVEL_RANK.get(str(level).upper(), 2)


def register(mcp: FastMCP, flags: FeatureFlags = DEFAULT_FLAGS) -> None:
    """Register all repairs and core tools on the MCP server."""

    tool = make_registrar(mcp, flags)

    @tool(
        ToolKind.CORE_READ,
        annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
    )
    async def get_repairs_issues(
        ctx: Context,
        include_dismissed: bool = False,
        instance: str = "",
    ) -> list[dict[str, Any]]:
        """
        List repair issues reported by Home Assistant.

        Reads the repair issues via the WebSocket ``repairs/list_issues``
        command, which returns ``{"issues": [...]}`` (empty -> ``{"issues":
        []}``). Each issue includes issue_id, domain, translation_key,
        severity, breaks_in_ha_version, and more. When ``include_dismissed``
        is False (the default), issues whose ``ignored`` flag is True are
        filtered out; when True, all issues are returned.

        Args:
            ctx: MCP request context (injected by FastMCP).
            include_dismissed: When True, include dismissed issues. Defaults to
                                False, which filters out dismissed issues.
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            List of repair issue dicts.
        """

        state = ctx.request_context.lifespan_context
        client: HomeAssistantClient = state.clients[instance or state.default_instance]
        result = await client.ws_command("repairs/list_issues")
        issues: list[dict[str, Any]] = (
            result.get("issues", []) if isinstance(result, dict) else list(result)
        )
        if not include_dismissed:
            issues = [i for i in issues if i.get("ignored") is not True]
        return issues

    @tool(
        ToolKind.CORE_READ,
        annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
    )
    async def get_repairs_issue_detail(
        ctx: Context,
        domain: str,
        issue_id: str,
        instance: str = "",
    ) -> dict[str, Any]:
        """
        Get the detail of a single repair issue.

        Reads the single issue via the WebSocket ``repairs/get_issue_data``
        command, using the issue's ``domain`` and ``issue_id``.

        Args:
            ctx: MCP request context (injected by FastMCP).
            domain: The repair issue's domain.
            issue_id: The repair issue ID.
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            The repair issue detail object.
        """

        state = ctx.request_context.lifespan_context
        client: HomeAssistantClient = state.clients[instance or state.default_instance]
        result: dict[str, Any] = await client.ws_command(
            "repairs/get_issue_data", domain=domain, issue_id=issue_id
        )
        return result

    @tool(
        ToolKind.CORE_READ,
        annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
    )
    async def get_core_version(
        ctx: Context,
        instance: str = "",
    ) -> dict[str, Any]:
        """
        Get the Home Assistant core version.

        Args:
            ctx: MCP request context (injected by FastMCP).
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            A dict with the version key.
        """

        state = ctx.request_context.lifespan_context
        client: HomeAssistantClient = state.clients[instance or state.default_instance]
        config: dict[str, Any] = await client.get("/api/config")
        return {"version": config.get("version")}

    @tool(
        ToolKind.CORE_READ,
        annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
    )
    async def list_loaded_integrations(
        ctx: Context,
        instance: str = "",
    ) -> list[dict[str, Any]]:
        """
        List loaded integrations with their domain, title, state, and source.

        Args:
            ctx: MCP request context (injected by FastMCP).
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            De-duplicated, sorted list of integration dicts with domain,
            title, state, and source.
        """

        state = ctx.request_context.lifespan_context
        client: HomeAssistantClient = state.clients[instance or state.default_instance]
        entries: list[dict[str, Any]] = await client.get(
            "/api/config/config_entries/entry"
        )
        mapped = [
            {
                "domain": e.get("domain"),
                "title": e.get("title"),
                "state": e.get("state"),
                "source": e.get("source"),
            }
            for e in entries
        ]
        seen: set[tuple[Any, Any, Any, Any]] = set()
        unique: list[dict[str, Any]] = []
        for entry in mapped:
            key = (entry["domain"], entry["title"], entry["state"], entry["source"])
            if key not in seen:
                seen.add(key)
                unique.append(entry)
        unique.sort(key=lambda d: (d["domain"] or "", d["title"] or ""))
        return unique

    @tool(
        ToolKind.CORE_READ,
        annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
    )
    async def get_ha_log(
        ctx: Context,
        tail: int = 100,
        min_level: str = "WARNING",
        instance: str = "",
    ) -> str:
        """
        Get the Home Assistant core log, filtered by severity level.

        Reads the core log via the WebSocket ``system_log/list`` command,
        which returns a list of structured entry dicts. Each entry has ``name``,
        ``message``, ``level`` (DEBUG/INFO/WARNING/ERROR/CRITICAL),
        ``timestamp``, and ``count``. Entries whose ``level`` rank is at or
        above ``min_level`` are kept, and the last ``tail`` matching entries
        are returned as a JSON string.

        Args:
            ctx: MCP request context (injected by FastMCP).
            tail: Maximum number of matching entries to return.
            min_level: Minimum severity level to keep (DEBUG, INFO, WARNING,
                       ERROR, or CRITICAL).
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            The filtered entries serialised as a JSON string.
        """

        state = ctx.request_context.lifespan_context
        client: HomeAssistantClient = state.clients[instance or state.default_instance]
        entries = await client.ws_command("system_log/list")
        if not isinstance(entries, list):
            return json.dumps(entries) if isinstance(entries, dict) else str(entries)
        min_rank = _level_rank(min_level)
        kept = [e for e in entries if _level_rank(e.get("level")) >= min_rank]
        return json.dumps(kept[-tail:])

    @tool(
        ToolKind.CORE_READ,
        annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
    )
    async def validate_config(
        ctx: Context,
        instance: str = "",
    ) -> dict[str, Any]:
        """
        Validate the Home Assistant YAML configuration files.

        This is a non-mutating validation call, so it is classified as a read.
        Uses the REST endpoint ``/api/config/core/check_config``.

        Args:
            ctx: MCP request context (injected by FastMCP).
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            Validation result with result ("valid" or "invalid") and an errors
            list.
        """

        state = ctx.request_context.lifespan_context
        client: HomeAssistantClient = state.clients[instance or state.default_instance]
        return await client.post("/api/config/core/check_config")

    @tool(
        ToolKind.RESTART,
        annotations=ToolAnnotations(destructiveHint=True, openWorldHint=True),
    )
    async def restart_core(
        ctx: Context,
        instance: str = "",
    ) -> str:
        """
        Restart the Home Assistant Core process.

        Args:
            ctx: MCP request context (injected by FastMCP).
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            Confirmation message.
        """

        state = ctx.request_context.lifespan_context
        client: HomeAssistantClient = state.clients[instance or state.default_instance]
        result = await client.post("/api/services/homeassistant/restart")
        return str(result)
