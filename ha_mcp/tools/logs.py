"""MCP tools for accessing Home Assistant system and component logs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ha_mcp.tools.gating import DEFAULT_FLAGS, ToolKind, make_registrar

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from ha_mcp.client import HomeAssistantClient
    from ha_mcp.config import FeatureFlags

_SUPERVISOR_PREFIX = "/api/hassio"


def register(mcp: FastMCP, flags: FeatureFlags = DEFAULT_FLAGS) -> None:
    """Register all log-access tools on the MCP server."""

    tool = make_registrar(mcp, flags)

    @tool(ToolKind.CORE_READ, annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    async def get_error_log(
        ctx: Context,
        instance: str = "",
    ) -> str:
        """
        Get the Home Assistant core error log.

        Args:
            ctx: MCP request context (injected by FastMCP).
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            Raw error log text from the HA logger.
        """

        state = ctx.request_context.lifespan_context
        client: HomeAssistantClient = state.clients[instance or state.default_instance]
        return await client.get("/api/error_log")

    @tool(ToolKind.SUPERVISOR_READ, annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    async def get_supervisor_logs(
        ctx: Context,
        instance: str = "",
    ) -> str:
        """
        Get logs from the Home Assistant Supervisor process.

        Requires a Supervisor-enabled installation (HA OS or Supervised).

        Args:
            ctx: MCP request context (injected by FastMCP).
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            Raw Supervisor log output.
        """

        state = ctx.request_context.lifespan_context
        client: HomeAssistantClient = state.clients[instance or state.default_instance]
        return await client.get(f"{_SUPERVISOR_PREFIX}/supervisor/logs")

    @tool(ToolKind.SUPERVISOR_READ, annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    async def get_core_logs(
        ctx: Context,
        instance: str = "",
    ) -> str:
        """
        Get logs from the Home Assistant Core process via Supervisor.

        Requires a Supervisor-enabled installation (HA OS or Supervised).

        Args:
            ctx: MCP request context (injected by FastMCP).
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            Raw Core process log output.
        """

        state = ctx.request_context.lifespan_context
        client: HomeAssistantClient = state.clients[instance or state.default_instance]
        return await client.get(f"{_SUPERVISOR_PREFIX}/core/logs")

    @tool(ToolKind.SUPERVISOR_READ, annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    async def get_host_logs(
        ctx: Context,
        instance: str = "",
    ) -> str:
        """
        Get system-level host logs from the underlying OS.

        Requires a Supervisor-enabled installation (HA OS or Supervised).

        Args:
            ctx: MCP request context (injected by FastMCP).
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            Raw host/journald log output.
        """

        state = ctx.request_context.lifespan_context
        client: HomeAssistantClient = state.clients[instance or state.default_instance]
        return await client.get(f"{_SUPERVISOR_PREFIX}/host/logs")

    @tool(ToolKind.SUPERVISOR_READ, annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    async def get_multicast_logs(
        ctx: Context,
        instance: str = "",
    ) -> str:
        """
        Get logs from the Home Assistant Multicast service.

        Requires a Supervisor-enabled installation (HA OS or Supervised).

        Args:
            ctx: MCP request context (injected by FastMCP).
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            Raw Multicast service log output.
        """

        state = ctx.request_context.lifespan_context
        client: HomeAssistantClient = state.clients[instance or state.default_instance]
        return await client.get(f"{_SUPERVISOR_PREFIX}/multicast/logs")
