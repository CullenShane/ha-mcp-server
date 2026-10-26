"""MCP tools for Home Assistant notifications and persistent messages."""

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
    """Register all notification tools on the MCP server."""

    tool = make_registrar(mcp, flags)

    @tool(ToolKind.CORE_READ, annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    async def list_notification_services(
        ctx: Context,
        instance: str = "",
    ) -> list[str]:
        """
        List all available notification service names in Home Assistant.

        Queries the HA services API and returns only the service names within
        the notify domain (e.g. notify, mobile_app_my_phone, pushbullet). Pass
        one of these names as the service argument to send_notification.
        Returns an empty list if no notifier integration is configured in Home
        Assistant.

        Args:
            ctx: MCP request context (injected by FastMCP).
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            List of notify service name strings.
        """

        state = ctx.request_context.lifespan_context
        client: HomeAssistantClient = state.clients[instance or state.default_instance]
        services: list[dict[str, Any]] = await client.get("/api/services")

        for domain_info in services:
            if domain_info.get("domain") == "notify":
                svc = domain_info.get("services", {})
                return list(svc.keys())

        return []

    @tool(ToolKind.CORE_WRITE, annotations=ToolAnnotations(openWorldHint=True))
    async def send_notification(
        ctx: Context,
        message: str,
        title: str | None = None,
        service: str = "notify",
        target: list[str] | None = None,
        data: dict[str, Any] | None = None,
        instance: str = "",
    ) -> list[dict[str, Any]]:
        """
        Send a notification via a Home Assistant notify service.

        Use list_notification_services to discover available service names. The
        default service value of "notify" targets the catch-all notifier
        (usually the first configured one). For mobile push notifications use
        the mobile_app_<device_name> service.

        Args:
            ctx: MCP request context (injected by FastMCP).
            message: Notification body text.
            title: Optional notification title.
            service: Notify service name, e.g. "notify" or
                     "mobile_app_my_phone".
            target: Optional list of targets (device IDs, group names)
                    supported by the chosen service.
            data: Optional service-specific extra payload. For
                  iOS/Android mobile push use {"push": {"sound": "default"}}.
                  For other services consult the integration docs for supported
                  keys.
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            List of entity states affected by the service call.
        """

        payload: dict[str, Any] = {"message": message}
        if title is not None:
            payload["title"] = title
        if target is not None:
            payload["target"] = target
        if data is not None:
            payload["data"] = data

        lifespan = ctx.request_context.lifespan_context
        client: HomeAssistantClient = lifespan.clients[instance or lifespan.default_instance]
        return await client.post(f"/api/services/notify/{service}", payload)

    @tool(ToolKind.CORE_READ, annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    async def list_persistent_notifications(
        ctx: Context,
        instance: str = "",
    ) -> list[dict[str, Any]]:
        """
        List all active persistent notifications shown in the HA UI bell menu.

        Persistent notifications remain visible in the HA frontend until
        explicitly dismissed. Each entry has a notification_id (in the
        entity_id as persistent_notification.<id>) and attributes
        containing message, title, and created_at.

        Args:
            ctx: MCP request context (injected by FastMCP).
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            List of persistent notification state objects.
        """

        state = ctx.request_context.lifespan_context
        client: HomeAssistantClient = state.clients[instance or state.default_instance]
        states: list[dict[str, Any]] = await client.get("/api/states")
        return [
            s for s in states if s["entity_id"].startswith("persistent_notification.")
        ]

    @tool(ToolKind.CORE_WRITE, annotations=ToolAnnotations(openWorldHint=True))
    async def create_persistent_notification(
        ctx: Context,
        message: str,
        title: str | None = None,
        notification_id: str | None = None,
        instance: str = "",
    ) -> list[dict[str, Any]]:
        """
        Create a persistent notification in the Home Assistant UI.

        The notification appears in the bell menu and remains until dismissed.
        If notification_id is provided and a notification with that ID already
        exists, it will be replaced.

        Args:
            ctx: MCP request context (injected by FastMCP).
            message: Notification body text (supports Markdown).
            title: Optional notification title.
            notification_id: Optional stable ID for upsert behaviour. If
                             omitted HA generates a random one.
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            List of entity states affected by the service call.
        """

        payload: dict[str, Any] = {"message": message}
        if title is not None:
            payload["title"] = title
        if notification_id is not None:
            payload["notification_id"] = notification_id

        lifespan = ctx.request_context.lifespan_context
        client: HomeAssistantClient = lifespan.clients[instance or lifespan.default_instance]
        return await client.post(
            "/api/services/persistent_notification/create", payload
        )

    @tool(ToolKind.CORE_WRITE, annotations=ToolAnnotations(destructiveHint=True, openWorldHint=True))
    async def dismiss_persistent_notification(
        ctx: Context,
        notification_id: str,
        instance: str = "",
    ) -> list[dict[str, Any]]:
        """
        Dismiss a persistent notification from the Home Assistant UI.

        Args:
            ctx: MCP request context (injected by FastMCP).
            notification_id: The notification ID (the part after
                             persistent_notification. in the entity ID).
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            List of entity states affected by the service call.
        """

        lifespan = ctx.request_context.lifespan_context
        client: HomeAssistantClient = lifespan.clients[instance or lifespan.default_instance]
        return await client.post(
            "/api/services/persistent_notification/dismiss",
            {"notification_id": notification_id},
        )
