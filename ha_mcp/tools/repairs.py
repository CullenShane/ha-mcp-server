"""MCP tools for Home Assistant repairs, logs, and core configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ha_mcp.tools.gating import DEFAULT_FLAGS, ToolKind, make_registrar

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from ha_mcp.client import HomeAssistantClient
    from ha_mcp.config import FeatureFlags

# Log severity tokens in ascending order. Used by get_ha_log to filter lines.
_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")


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

        Returns the repair issues from the HA repairs API. Each issue includes
        issue_id, domain, translation_key, severity, breaks_in_ha_version,
        entity_id, and data. The HA REST endpoint returns open issues; the
        include_dismissed flag is accepted for forward-compatibility. When it is
        False (the default), issues whose dismissed_version field is present and
        non-null are filtered out; when True, all issues are returned.

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
        response: dict[str, Any] | list[dict[str, Any]] = await client.get(
            "/api/repairs/issues"
        )
        if isinstance(response, list):
            issues: list[dict[str, Any]] = response
        else:
            issues = response.get("issues", [])
        if not include_dismissed:
            issues = [i for i in issues if not i.get("dismissed_version")]
        return issues

    @tool(
        ToolKind.CORE_READ,
        annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
    )
    async def get_repairs_issue_detail(
        ctx: Context,
        issue_id: str,
        instance: str = "",
    ) -> dict[str, Any]:
        """
        Get the detail of a single repair issue.

        Args:
            ctx: MCP request context (injected by FastMCP).
            issue_id: The repair issue ID.
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            The repair issue detail object.
        """

        state = ctx.request_context.lifespan_context
        client: HomeAssistantClient = state.clients[instance or state.default_instance]
        response: dict[str, Any] = await client.get(
            f"/api/repairs/issue_registry/{issue_id}"
        )
        return response.get("data", response)

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
        Get the Home Assistant log, filtered by severity level.

        Reads the HA log and returns the last ``tail`` lines at or above
        ``min_level`` in severity (DEBUG < INFO < WARNING < ERROR). A line
        matches if it contains the literal level token. When ``min_level`` is
        DEBUG all lines are kept.

        Args:
            ctx: MCP request context (injected by FastMCP).
            tail: Maximum number of matching lines to return.
            min_level: Minimum severity level to keep (DEBUG, INFO, WARNING,
                       or ERROR).
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            The filtered log lines joined by newlines.
        """

        state = ctx.request_context.lifespan_context
        client: HomeAssistantClient = state.clients[instance or state.default_instance]
        response = await client.get("/api/log")
        if isinstance(response, dict):
            text: str = response.get("log_full") or response.get("log_small") or ""
        else:
            text = str(response)
        lines = text.splitlines()
        level = min_level.upper()
        if level == "DEBUG":
            matching = lines
        else:
            tokens = _LEVELS[_LEVELS.index(level) :]
            matching = [line for line in lines if any(tok in line for tok in tokens)]
        return "\n".join(matching[-tail:])

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
        return await client.post("/api/config/check")

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
