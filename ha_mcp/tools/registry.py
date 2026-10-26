"""MCP tools for the Home Assistant device and config-entry registries."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ha_mcp.tools.gating import DEFAULT_FLAGS, ToolKind, make_registrar

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from ha_mcp.client import HomeAssistantClient
    from ha_mcp.config import FeatureFlags


def register(mcp: FastMCP, flags: FeatureFlags = DEFAULT_FLAGS) -> None:
    """Register all registry tools on the MCP server."""

    tool = make_registrar(mcp, flags)

    @tool(ToolKind.CORE_READ, annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    async def get_device_registry(
        ctx: Context,
        instance: str = "",
    ) -> list[dict[str, Any]]:
        """
        List all devices in the Home Assistant device registry.

        Returns hardware-level device information sourced from the device
        registry, not the state machine. Each entry includes id, name,
        manufacturer, model, sw_version, hw_version, area_id, and the list of
        config_entries the device belongs to. Use this to identify physical
        devices by manufacturer and model rather than by entity ID.

        The HA REST API may return either a bare list or a dict with a devices
        key depending on the HA version. This tool normalises both forms to a
        plain list.

        Args:
            ctx: MCP request context (injected by FastMCP).
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            List of device registry entries.
        """

        state = ctx.request_context.lifespan_context
        client: HomeAssistantClient = state.clients[instance or state.default_instance]
        response: list[dict[str, Any]] | dict[str, Any] = await client.get(
            "/api/config/device_registry/list"
        )
        return (
            response.get("devices", response)
            if isinstance(response, dict)
            else response
        )

    @tool(ToolKind.CORE_READ, annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    async def list_config_entries(
        ctx: Context,
        instance: str = "",
    ) -> list[dict[str, Any]]:
        """
        List all integration config entries loaded in Home Assistant.

        Config entries represent installed integrations (e.g. Philips Hue,
        Google Cast, MQTT). Each entry includes entry_id, domain, title,
        disabled_by, and state. Possible state values: loaded, setup_error,
        migration_error, setup_retry, failed_unload, not_loaded, disabled.
        Use entry_id with reload_config_entry to reload a specific integration
        without restarting HA.

        Args:
            ctx: MCP request context (injected by FastMCP).
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            List of config entry objects.
        """

        state = ctx.request_context.lifespan_context
        client: HomeAssistantClient = state.clients[instance or state.default_instance]
        return await client.get("/api/config/config_entries/entry")

    @tool(ToolKind.CORE_WRITE, annotations=ToolAnnotations(openWorldHint=True))
    async def reload_config_entry(
        ctx: Context,
        entry_id: str,
        instance: str = "",
    ) -> dict[str, Any]:
        """
        Reload a single integration config entry without restarting HA.

        Triggers HA to unload and re-initialise the integration identified by
        entry_id. Useful for applying config changes or recovering a broken
        integration without a full restart. Obtain entry_id from
        list_config_entries.

        Args:
            ctx: MCP request context (injected by FastMCP).
            entry_id: Config entry ID, e.g. "a1b2c3d4e5f6...".
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            Result object with a require_restart boolean indicating whether a
            full HA restart is still needed.
        """

        state = ctx.request_context.lifespan_context
        client: HomeAssistantClient = state.clients[instance or state.default_instance]
        return await client.post(
            f"/api/config/config_entries/entry/{entry_id}/reload"
        )
