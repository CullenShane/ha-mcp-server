"""
MCP tools for Home Assistant Supervisor add-on management.

These tools require a Supervisor-enabled installation (e.g. Home Assistant OS
or Supervised). They use the Supervisor API at /api/hassio/.
"""

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
    """Register all add-on management tools on the MCP server."""

    tool = make_registrar(mcp, flags)

    @tool(ToolKind.HASSIO_READ, annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    async def list_addons(
        ctx: Context,
        instance: str = "",
    ) -> list[dict[str, Any]]:
        """
        List all available and installed Home Assistant add-ons.

        Requires a Supervisor-enabled installation (HA OS or Supervised). Use
        get_addon_info to retrieve full details for a specific add-on, or
        set_addon_options to configure one.

        Args:
            ctx: MCP request context (injected by FastMCP).
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            List of add-on summary objects with slug, name, state, version,
            version_latest, and update_available.
        """

        state = ctx.request_context.lifespan_context
        client: HomeAssistantClient = state.clients[instance or state.default_instance]
        response: dict[str, Any] = await client.get(f"{_SUPERVISOR_PREFIX}/addons")
        return response.get("data", {}).get("addons", [])

    @tool(ToolKind.HASSIO_READ, annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    async def get_addon_info(
        ctx: Context,
        addon_slug: str,
        instance: str = "",
    ) -> dict[str, Any]:
        """
        Get detailed information about a specific add-on.

        Requires a Supervisor-enabled installation (HA OS or Supervised). Use
        get_addon_logs to inspect runtime output, or set_addon_options to
        change configuration.

        Args:
            ctx: MCP request context (injected by FastMCP).
            addon_slug: Add-on slug identifier, e.g. core_mosquitto or
                        a0d7b954_vscode.
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            Detailed add-on info including version, state, options, ports, and
            ingress config.
        """

        state = ctx.request_context.lifespan_context
        client: HomeAssistantClient = state.clients[instance or state.default_instance]
        response: dict[str, Any] = await client.get(
            f"{_SUPERVISOR_PREFIX}/addons/{addon_slug}/info"
        )
        return response.get("data", response)

    @tool(ToolKind.HASSIO_WRITE, annotations=ToolAnnotations(openWorldHint=True))
    async def install_addon(
        ctx: Context,
        addon_slug: str,
        instance: str = "",
    ) -> str:
        """
        Install a Home Assistant add-on from the store.

        Requires a Supervisor-enabled installation (HA OS or Supervised).

        Args:
            ctx: MCP request context (injected by FastMCP).
            addon_slug: Add-on slug to install, e.g. core_ssh.
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            Confirmation message.
        """

        state = ctx.request_context.lifespan_context
        client: HomeAssistantClient = state.clients[instance or state.default_instance]
        response: dict[str, Any] = await client.post(
            f"{_SUPERVISOR_PREFIX}/addons/{addon_slug}/install"
        )
        return response.get("result", str(response))

    @tool(ToolKind.HASSIO_WRITE, annotations=ToolAnnotations(destructiveHint=True, openWorldHint=True))
    async def uninstall_addon(
        ctx: Context,
        addon_slug: str,
        instance: str = "",
    ) -> str:
        """
        Uninstall a Home Assistant add-on. This action is irreversible.

        Requires a Supervisor-enabled installation (HA OS or Supervised).

        Args:
            ctx: MCP request context (injected by FastMCP).
            addon_slug: Add-on slug to remove.
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            Confirmation message.
        """

        state = ctx.request_context.lifespan_context
        client: HomeAssistantClient = state.clients[instance or state.default_instance]
        response: dict[str, Any] = await client.post(
            f"{_SUPERVISOR_PREFIX}/addons/{addon_slug}/uninstall"
        )
        return response.get("result", str(response))

    @tool(ToolKind.HASSIO_WRITE, annotations=ToolAnnotations(openWorldHint=True))
    async def update_addon(
        ctx: Context,
        addon_slug: str,
        instance: str = "",
    ) -> str:
        """
        Update a Home Assistant add-on to the latest available version.

        Requires a Supervisor-enabled installation (HA OS or Supervised).

        Args:
            ctx: MCP request context (injected by FastMCP).
            addon_slug: Add-on slug to update.
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            Confirmation message.
        """

        state = ctx.request_context.lifespan_context
        client: HomeAssistantClient = state.clients[instance or state.default_instance]
        response: dict[str, Any] = await client.post(
            f"{_SUPERVISOR_PREFIX}/addons/{addon_slug}/update"
        )
        return response.get("result", str(response))

    @tool(ToolKind.HASSIO_WRITE, annotations=ToolAnnotations(openWorldHint=True))
    async def start_addon(
        ctx: Context,
        addon_slug: str,
        instance: str = "",
    ) -> str:
        """
        Start a stopped Home Assistant add-on.

        Requires a Supervisor-enabled installation (HA OS or Supervised).

        Args:
            ctx: MCP request context (injected by FastMCP).
            addon_slug: Add-on slug to start.
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            Confirmation message.
        """

        state = ctx.request_context.lifespan_context
        client: HomeAssistantClient = state.clients[instance or state.default_instance]
        response: dict[str, Any] = await client.post(
            f"{_SUPERVISOR_PREFIX}/addons/{addon_slug}/start"
        )
        return response.get("result", str(response))

    @tool(ToolKind.HASSIO_WRITE, annotations=ToolAnnotations(openWorldHint=True))
    async def stop_addon(
        ctx: Context,
        addon_slug: str,
        instance: str = "",
    ) -> str:
        """
        Stop a running Home Assistant add-on.

        Requires a Supervisor-enabled installation (HA OS or Supervised).

        Args:
            ctx: MCP request context (injected by FastMCP).
            addon_slug: Add-on slug to stop.
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            Confirmation message.
        """

        state = ctx.request_context.lifespan_context
        client: HomeAssistantClient = state.clients[instance or state.default_instance]
        response: dict[str, Any] = await client.post(
            f"{_SUPERVISOR_PREFIX}/addons/{addon_slug}/stop"
        )
        return response.get("result", str(response))

    @tool(ToolKind.HASSIO_WRITE, annotations=ToolAnnotations(openWorldHint=True))
    async def restart_addon(
        ctx: Context,
        addon_slug: str,
        instance: str = "",
    ) -> str:
        """
        Restart a Home Assistant add-on.

        Requires a Supervisor-enabled installation (HA OS or Supervised).

        Args:
            ctx: MCP request context (injected by FastMCP).
            addon_slug: Add-on slug to restart.
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            Confirmation message.
        """

        state = ctx.request_context.lifespan_context
        client: HomeAssistantClient = state.clients[instance or state.default_instance]
        response: dict[str, Any] = await client.post(
            f"{_SUPERVISOR_PREFIX}/addons/{addon_slug}/restart"
        )
        return response.get("result", str(response))

    @tool(ToolKind.HASSIO_READ, annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    async def get_addon_logs(
        ctx: Context,
        addon_slug: str,
        instance: str = "",
    ) -> str:
        """
        Fetch the stdout/stderr logs for a specific add-on.

        Requires a Supervisor-enabled installation (HA OS or Supervised).
        Returns an empty string if the add-on has never started or has no log
        output.

        Args:
            ctx: MCP request context (injected by FastMCP).
            addon_slug: Add-on slug whose logs to retrieve.
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            Raw log output as a string.
        """

        state = ctx.request_context.lifespan_context
        client: HomeAssistantClient = state.clients[instance or state.default_instance]
        return await client.get(f"{_SUPERVISOR_PREFIX}/addons/{addon_slug}/logs")

    @tool(ToolKind.HASSIO_WRITE, annotations=ToolAnnotations(openWorldHint=True))
    async def set_addon_options(
        ctx: Context,
        addon_slug: str,
        options: dict[str, Any],
        instance: str = "",
    ) -> str:
        """
        Update configuration options for a Home Assistant add-on.

        Requires a Supervisor-enabled installation (HA OS or Supervised). The
        add-on must be restarted after updating options for changes to take
        effect. Use get_addon_info to inspect the current options schema.

        Args:
            ctx: MCP request context (injected by FastMCP).
            addon_slug: Add-on slug to configure.
            options: Dictionary of option keys and values specific to the
                     add-on.
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            Confirmation message.
        """

        state = ctx.request_context.lifespan_context
        client: HomeAssistantClient = state.clients[instance or state.default_instance]
        response: dict[str, Any] = await client.post(
            f"{_SUPERVISOR_PREFIX}/addons/{addon_slug}/options",
            {"options": options},
        )
        return response.get("result", str(response))

    @tool(ToolKind.HASSIO_READ, annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    async def list_addon_repositories(
        ctx: Context,
        instance: str = "",
    ) -> list[dict[str, Any]]:
        """
        List all configured add-on repositories (stores).

        Requires a Supervisor-enabled installation (HA OS or Supervised).

        Args:
            ctx: MCP request context (injected by FastMCP).
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            List of repository objects with slug, name, source, and maintainer.
        """

        state = ctx.request_context.lifespan_context
        client: HomeAssistantClient = state.clients[instance or state.default_instance]
        response: dict[str, Any] = await client.get(
            f"{_SUPERVISOR_PREFIX}/store/repositories"
        )
        return response.get("data", {}).get("repositories", [])

    @tool(ToolKind.HASSIO_WRITE, annotations=ToolAnnotations(openWorldHint=True))
    async def add_addon_repository(
        ctx: Context,
        repository_url: str,
        instance: str = "",
    ) -> str:
        """
        Add a third-party add-on repository to Home Assistant.

        Requires a Supervisor-enabled installation (HA OS or Supervised).
        Only HTTPS URLs are accepted to prevent sending unvalidated schemes
        (e.g. file:// or javascript:) to the Supervisor.

        Args:
            ctx: MCP request context (injected by FastMCP).
            repository_url: HTTPS Git URL of the repository,
                            e.g. https://github.com/owner/repo.
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            Confirmation message.

        Raises:
            ValueError: If repository_url does not start with https://.
        """

        if not repository_url.startswith("https://"):
            raise ValueError(
                "repository_url must start with https://, "
                f"got {repository_url!r}"
            )

        state = ctx.request_context.lifespan_context
        client: HomeAssistantClient = state.clients[instance or state.default_instance]
        response: dict[str, Any] = await client.post(
            f"{_SUPERVISOR_PREFIX}/store/repositories",
            {"repository": repository_url},
        )
        return response.get("result", str(response))
