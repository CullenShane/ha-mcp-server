"""MCP tools for Home Assistant automation and script management."""

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
    """Register all automation and script tools on the MCP server."""

    tool = make_registrar(mcp, flags)

    @tool(ToolKind.CORE_READ, annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    async def list_automations(
        ctx: Context,
        instance: str = "",
    ) -> list[dict[str, Any]]:
        """
        List all automations defined in Home Assistant.

        Args:
            ctx: MCP request context (injected by FastMCP).
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            List of automation state objects. Each has entity_id, state
            (on/off), and attributes with friendly_name and last_triggered.
        """

        state = ctx.request_context.lifespan_context
        client: HomeAssistantClient = state.clients[instance or state.default_instance]
        states: list[dict[str, Any]] = await client.get("/api/states")
        return [s for s in states if s["entity_id"].startswith("automation.")]

    @tool(ToolKind.CORE_WRITE, annotations=ToolAnnotations(openWorldHint=True))
    async def trigger_automation(
        ctx: Context,
        entity_id: str,
        instance: str = "",
    ) -> list[dict[str, Any]]:
        """
        Manually trigger an automation regardless of its conditions.

        Args:
            ctx: MCP request context (injected by FastMCP).
            entity_id: Automation entity ID, e.g. automation.morning_lights.
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            List of affected entity states.
        """

        state = ctx.request_context.lifespan_context
        client: HomeAssistantClient = state.clients[instance or state.default_instance]
        return await client.post(
            "/api/services/automation/trigger",
            {"entity_id": entity_id},
        )

    @tool(ToolKind.CORE_WRITE, annotations=ToolAnnotations(openWorldHint=True))
    async def enable_automation(
        ctx: Context,
        entity_id: str,
        instance: str = "",
    ) -> list[dict[str, Any]]:
        """
        Enable a previously disabled automation.

        Args:
            ctx: MCP request context (injected by FastMCP).
            entity_id: Automation entity ID, e.g. automation.morning_lights.
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            List of affected entity states.
        """

        state = ctx.request_context.lifespan_context
        client: HomeAssistantClient = state.clients[instance or state.default_instance]
        return await client.post(
            "/api/services/automation/turn_on",
            {"entity_id": entity_id},
        )

    @tool(ToolKind.CORE_WRITE, annotations=ToolAnnotations(openWorldHint=True))
    async def disable_automation(
        ctx: Context,
        entity_id: str,
        instance: str = "",
    ) -> list[dict[str, Any]]:
        """
        Disable an automation so it will not fire automatically.

        Args:
            ctx: MCP request context (injected by FastMCP).
            entity_id: Automation entity ID.
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            List of affected entity states.
        """

        state = ctx.request_context.lifespan_context
        client: HomeAssistantClient = state.clients[instance or state.default_instance]
        return await client.post(
            "/api/services/automation/turn_off",
            {"entity_id": entity_id},
        )

    @tool(ToolKind.CORE_WRITE, annotations=ToolAnnotations(openWorldHint=True))
    async def reload_automations(
        ctx: Context,
        instance: str = "",
    ) -> str:
        """
        Reload all automations from the YAML configuration without restarting HA.

        Args:
            ctx: MCP request context (injected by FastMCP).
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            Confirmation message.
        """

        state = ctx.request_context.lifespan_context
        client: HomeAssistantClient = state.clients[instance or state.default_instance]
        result = await client.post("/api/services/automation/reload")
        return f"Automations reloaded. Affected states: {len(result)}"

    @tool(ToolKind.CORE_READ, annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    async def list_scripts(
        ctx: Context,
        instance: str = "",
    ) -> list[dict[str, Any]]:
        """
        List all scripts defined in Home Assistant.

        Args:
            ctx: MCP request context (injected by FastMCP).
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            List of script state objects with entity_id, state, and attributes.
        """

        state = ctx.request_context.lifespan_context
        client: HomeAssistantClient = state.clients[instance or state.default_instance]
        states: list[dict[str, Any]] = await client.get("/api/states")
        return [s for s in states if s["entity_id"].startswith("script.")]

    @tool(ToolKind.CORE_WRITE, annotations=ToolAnnotations(openWorldHint=True))
    async def run_script(
        ctx: Context,
        entity_id: str,
        variables: dict[str, Any] | None = None,
        instance: str = "",
    ) -> list[dict[str, Any]]:
        """
        Execute a HA script entity.

        Args:
            ctx: MCP request context (injected by FastMCP).
            entity_id: Script entity ID, e.g. script.goodnight.
            variables: Optional variables to pass into the script.
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            List of affected entity states.
        """

        state = ctx.request_context.lifespan_context
        client: HomeAssistantClient = state.clients[instance or state.default_instance]
        payload: dict[str, Any] = {"entity_id": entity_id}
        if variables:
            payload["variables"] = variables

        return await client.post("/api/services/script/turn_on", payload)

    @tool(ToolKind.CORE_READ, annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    async def list_scenes(
        ctx: Context,
        instance: str = "",
    ) -> list[dict[str, Any]]:
        """
        List all scenes defined in Home Assistant.

        Args:
            ctx: MCP request context (injected by FastMCP).
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            List of scene state objects.
        """

        state = ctx.request_context.lifespan_context
        client: HomeAssistantClient = state.clients[instance or state.default_instance]
        states: list[dict[str, Any]] = await client.get("/api/states")
        return [s for s in states if s["entity_id"].startswith("scene.")]

    @tool(ToolKind.CORE_WRITE, annotations=ToolAnnotations(openWorldHint=True))
    async def activate_scene(
        ctx: Context,
        entity_id: str,
        instance: str = "",
    ) -> list[dict[str, Any]]:
        """
        Activate a Home Assistant scene.

        Args:
            ctx: MCP request context (injected by FastMCP).
            entity_id: Scene entity ID, e.g. scene.movie_time.
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            List of affected entity states.
        """

        state = ctx.request_context.lifespan_context
        client: HomeAssistantClient = state.clients[instance or state.default_instance]
        return await client.post(
            "/api/services/scene/turn_on",
            {"entity_id": entity_id},
        )
