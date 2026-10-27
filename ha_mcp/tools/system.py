"""MCP tools for Home Assistant system information, configuration, and updates."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ha_mcp.tools.gating import DEFAULT_FLAGS, ToolKind, make_registrar

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from ha_mcp.client import HomeAssistantClient
    from ha_mcp.config import FeatureFlags

_SUPERVISOR_PREFIX = "/api/hassio"


def register(mcp: FastMCP, flags: FeatureFlags = DEFAULT_FLAGS) -> None:
    """Register all system and configuration tools on the MCP server."""

    tool = make_registrar(mcp, flags)

    @tool(
        ToolKind.CORE_READ,
        annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
    )
    async def get_ha_config(
        ctx: Context,
        instance: str = "",
    ) -> dict[str, Any]:
        """
        Get the current Home Assistant core configuration.

        Args:
            ctx: MCP request context (injected by FastMCP).
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            Config object including version, location_name, latitude,
            longitude, unit_system, time_zone, components, and more.
        """

        state = ctx.request_context.lifespan_context
        client: HomeAssistantClient = state.clients[instance or state.default_instance]
        return await client.get("/api/config")

    @tool(
        ToolKind.CORE_READ,
        annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
    )
    async def check_config(
        ctx: Context,
        instance: str = "",
    ) -> dict[str, Any]:
        """
        Validate the Home Assistant YAML configuration files.

        Args:
            ctx: MCP request context (injected by FastMCP).
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            Validation result with result ("valid" or "invalid") and an errors
            list of human-readable strings describing each problem, including
            YAML parse errors and unknown keys.
        """

        state = ctx.request_context.lifespan_context
        client: HomeAssistantClient = state.clients[instance or state.default_instance]
        return await client.post("/api/config/core/check_config")

    @tool(
        ToolKind.RESTART,
        annotations=ToolAnnotations(destructiveHint=True, openWorldHint=True),
    )
    async def restart_ha(
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
        result = await client.post("/api/config/core/restart")
        return str(result)

    @tool(
        ToolKind.HASSIO_READ,
        annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
    )
    async def get_supervisor_info(
        ctx: Context,
        instance: str = "",
    ) -> dict[str, Any]:
        """
        Get Supervisor system information including version and update status.

        Requires a Supervisor-enabled installation (HA OS or Supervised). Use
        the returned version_latest field to decide whether to call
        update_supervisor.

        Args:
            ctx: MCP request context (injected by FastMCP).
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            Supervisor info dict with versions, channel, and update availability.
        """

        state = ctx.request_context.lifespan_context
        client: HomeAssistantClient = state.clients[instance or state.default_instance]
        response: dict[str, Any] = await client.get(
            f"{_SUPERVISOR_PREFIX}/supervisor/info"
        )
        return response.get("data", response)

    @tool(
        ToolKind.HASSIO_READ,
        annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
    )
    async def get_core_info(
        ctx: Context,
        instance: str = "",
    ) -> dict[str, Any]:
        """
        Get Home Assistant Core process information via the Supervisor.

        Requires a Supervisor-enabled installation (HA OS or Supervised). Use
        the returned version_latest field to decide whether to call update_core.

        Args:
            ctx: MCP request context (injected by FastMCP).
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            Core info including version, update availability, and boot state.
        """

        state = ctx.request_context.lifespan_context
        client: HomeAssistantClient = state.clients[instance or state.default_instance]
        response: dict[str, Any] = await client.get(f"{_SUPERVISOR_PREFIX}/core/info")
        return response.get("data", response)

    @tool(
        ToolKind.HASSIO_READ,
        annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
    )
    async def get_host_info(
        ctx: Context,
        instance: str = "",
    ) -> dict[str, Any]:
        """
        Get information about the underlying host OS.

        Requires a Supervisor-enabled installation (HA OS or Supervised).

        Args:
            ctx: MCP request context (injected by FastMCP).
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            Host info including hostname, OS version, CPU usage, and memory.
        """

        state = ctx.request_context.lifespan_context
        client: HomeAssistantClient = state.clients[instance or state.default_instance]
        response: dict[str, Any] = await client.get(f"{_SUPERVISOR_PREFIX}/host/info")
        return response.get("data", response)

    @tool(
        ToolKind.HASSIO_READ,
        annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
    )
    async def get_os_info(
        ctx: Context,
        instance: str = "",
    ) -> dict[str, Any]:
        """
        Get Home Assistant OS information and update status.

        Requires a Supervisor-enabled installation (HA OS or Supervised). Use
        the returned version_latest field to decide whether to call update_os.

        Args:
            ctx: MCP request context (injected by FastMCP).
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            OS info with version and update availability.
        """

        state = ctx.request_context.lifespan_context
        client: HomeAssistantClient = state.clients[instance or state.default_instance]
        response: dict[str, Any] = await client.get(f"{_SUPERVISOR_PREFIX}/os/info")
        return response.get("data", response)

    @tool(ToolKind.HASSIO_WRITE, annotations=ToolAnnotations(openWorldHint=True))
    async def update_core(
        ctx: Context,
        instance: str = "",
    ) -> str:
        """
        Update the Home Assistant Core to the latest available version.

        Requires a Supervisor-enabled installation (HA OS or Supervised). Call
        get_core_info first to confirm an update is available.

        Args:
            ctx: MCP request context (injected by FastMCP).
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            Confirmation message.
        """

        state = ctx.request_context.lifespan_context
        client: HomeAssistantClient = state.clients[instance or state.default_instance]
        response: dict[str, Any] = await client.post(
            f"{_SUPERVISOR_PREFIX}/core/update"
        )
        return response.get("result", str(response))

    @tool(ToolKind.HASSIO_WRITE, annotations=ToolAnnotations(openWorldHint=True))
    async def update_supervisor(
        ctx: Context,
        instance: str = "",
    ) -> str:
        """
        Update the Home Assistant Supervisor to the latest version.

        Requires a Supervisor-enabled installation (HA OS or Supervised). Call
        get_supervisor_info first to confirm an update is available.

        Args:
            ctx: MCP request context (injected by FastMCP).
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            Confirmation message.
        """

        state = ctx.request_context.lifespan_context
        client: HomeAssistantClient = state.clients[instance or state.default_instance]
        response: dict[str, Any] = await client.post(
            f"{_SUPERVISOR_PREFIX}/supervisor/update"
        )
        return response.get("result", str(response))

    @tool(ToolKind.HASSIO_WRITE, annotations=ToolAnnotations(openWorldHint=True))
    async def update_os(
        ctx: Context,
        instance: str = "",
    ) -> str:
        """
        Update the Home Assistant OS to the latest version.

        Requires a Supervisor-enabled installation (HA OS or Supervised). Call
        get_os_info first to confirm an update is available.

        Args:
            ctx: MCP request context (injected by FastMCP).
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            Confirmation message.
        """

        state = ctx.request_context.lifespan_context
        client: HomeAssistantClient = state.clients[instance or state.default_instance]
        response: dict[str, Any] = await client.post(f"{_SUPERVISOR_PREFIX}/os/update")
        return response.get("result", str(response))

    @tool(
        ToolKind.CORE_READ,
        annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
    )
    async def list_integrations(
        ctx: Context,
        instance: str = "",
    ) -> list[dict[str, Any]]:
        """
        List all installed Home Assistant integrations.

        Args:
            ctx: MCP request context (injected by FastMCP).
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            List of integration config entries with domain,
            title, and state.
        """

        state = ctx.request_context.lifespan_context
        client: HomeAssistantClient = state.clients[instance or state.default_instance]
        return await client.get("/api/config/config_entries/entry")

    @tool(
        ToolKind.CORE_READ,
        annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
    )
    async def get_system_health(
        ctx: Context,
        instance: str = "",
    ) -> dict[str, Any] | None:
        """
        Get system health information for all components.

        Queries the Home Assistant WebSocket `system_health/info` command, as
        there is no REST route for health data in HA 2026.x. Returns the health
        dict keyed by component domain.

        Args:
            ctx: MCP request context (injected by FastMCP).
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            Health data keyed by component domain with status and metadata.
            Returns None when there are no issues.
        """

        state = ctx.request_context.lifespan_context
        client: HomeAssistantClient = state.clients[instance or state.default_instance]
        return await client.ws_command("system_health/info")

    @tool(
        ToolKind.CORE_READ,
        annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
    )
    async def list_users(
        ctx: Context,
        instance: str = "",
    ) -> list[dict[str, Any]]:
        """
        List all user accounts in Home Assistant.

        Args:
            ctx: MCP request context (injected by FastMCP).
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            List of user objects with id, name, is_active, and is_admin.
        """

        state = ctx.request_context.lifespan_context
        client: HomeAssistantClient = state.clients[instance or state.default_instance]
        return await client.get("/api/config/auth/users")

    @tool(ToolKind.HASSIO_WRITE, annotations=ToolAnnotations(openWorldHint=True))
    async def create_backup(
        ctx: Context,
        instance: str = "",
    ) -> dict[str, Any]:
        """
        Trigger the creation of a full Home Assistant backup.

        Requires a Supervisor-enabled installation (HA OS or Supervised).

        Args:
            ctx: MCP request context (injected by FastMCP).
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            Backup job info including the backup slug.
        """

        state = ctx.request_context.lifespan_context
        client: HomeAssistantClient = state.clients[instance or state.default_instance]
        response: dict[str, Any] = await client.post(
            f"{_SUPERVISOR_PREFIX}/backups/new/full"
        )
        return response.get("data", response)

    @tool(
        ToolKind.HASSIO_READ,
        annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
    )
    async def list_backups(
        ctx: Context,
        instance: str = "",
    ) -> list[dict[str, Any]]:
        """
        List all available Home Assistant backups.

        Requires a Supervisor-enabled installation (HA OS or Supervised).

        Args:
            ctx: MCP request context (injected by FastMCP).
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            List of backup objects with slug, name, date, size, and type.
        """

        state = ctx.request_context.lifespan_context
        client: HomeAssistantClient = state.clients[instance or state.default_instance]
        response: dict[str, Any] = await client.get(f"{_SUPERVISOR_PREFIX}/backups")
        return response.get("data", {}).get("backups", [])
