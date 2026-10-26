"""
Home Assistant MCP server entry point.

Loads configuration from a YAML file or environment variables and registers
all tool modules.

Usage:
    uv run ha-mcp

Configuration (in order of precedence):
    HA_CONFIG: Path to a YAML or JSON config file with multiple instances.
    ha-mcp.yaml: Config file in the current directory (auto-discovered).
    HA_URL + HA_TOKEN: Single-instance fallback via environment variables.

Config file format (ha-mcp.yaml):
    instances:
      - name: home
        url: http://homeassistant.local:8123
        token: <long-lived access token>
      - name: office
        url: http://office-ha.local:8123
        token: <long-lived access token>
    default: home  # optional; defaults to the first instance
"""

from __future__ import annotations

from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
import os
from typing import TYPE_CHECKING, Literal

from mcp.server.fastmcp import FastMCP

from ha_mcp.client import HomeAssistantClient
from ha_mcp.config import FeatureFlags, load_config, load_flags
from ha_mcp.tools import (
    addons,
    automations,
    dashboards,
    entities,
    helpers,
    logs,
    notifications,
    registry,
    repairs,
    system,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

_VALID_TRANSPORTS: tuple[Literal["stdio", "sse", "streamable-http"], ...] = (
    "stdio",
    "sse",
    "streamable-http",
)


@dataclass
class AppState:
    """Lifespan state shared across all tool calls."""

    clients: dict[str, HomeAssistantClient]
    default_instance: str


@asynccontextmanager
async def app_lifespan(app: FastMCP) -> AsyncIterator[AppState]:
    """
    Open one persistent HTTP session per configured HA instance.

    Yields an AppState whose clients dict maps instance names to open
    HomeAssistantClient sessions. Tools resolve the target client by
    looking up the instance name passed by the caller.
    """

    config = load_config()
    async with AsyncExitStack() as stack:
        clients: dict[str, HomeAssistantClient] = {}
        for inst in config.instances:
            client = await stack.enter_async_context(
                HomeAssistantClient(base_url=inst.url, token=inst.token)
            )
            clients[inst.name] = client
        yield AppState(clients=clients, default_instance=config.default)


def create_server(
    port: int = 8000,
    flags: FeatureFlags | None = None,
) -> FastMCP:
    """
    Create and configure the FastMCP server with all permitted tools registered.

    Args:
        port: TCP port for SSE transport. Ignored in stdio mode.
        flags: Feature gates controlling which tools are registered. Resolved
               from the environment via load_flags() when omitted.

    Returns:
        Configured FastMCP server instance.
    """

    flags = flags if flags is not None else load_flags()

    mcp = FastMCP(
        name="home-assistant",
        host="0.0.0.0",
        port=port,
        lifespan=app_lifespan,
        instructions=(
            "You are connected to a Home Assistant instance. "
            "You can inspect entities, automations, scripts, scenes, logs, "
            "the integration registry, repairs issues, the running core "
            "version, and validate configuration. "
            "This server is read-only by default: control tools (state, "
            "services, dashboards, automation triggers, notifications) are "
            "only available when HA_READONLY=false, restart_core only when "
            "HA_ENABLE_RESTART=true, and Supervisor tools (add-ons, updates, "
            "backups) only when HA_ENABLE_SUPERVISOR=true. "
            "Use call_service for controlling physical devices. "
            "Use set_entity_state only for virtual/input entities. "
            "Supervisor tools require HA OS or a Supervised installation and "
            "will fail on a Container install."
        ),
    )

    entities.register(mcp, flags)
    dashboards.register(mcp, flags)
    addons.register(mcp, flags)
    logs.register(mcp, flags)
    automations.register(mcp, flags)
    system.register(mcp, flags)
    notifications.register(mcp, flags)
    helpers.register(mcp, flags)
    registry.register(mcp, flags)
    repairs.register(mcp, flags)

    return mcp


def main() -> None:
    """
    Run the Home Assistant MCP server.

    Reads the TRANSPORT environment variable to select the transport. Defaults
    to stdio. When set to sse, binds an HTTP server on the port given by PORT
    (default 8765). Raises ValueError for any other TRANSPORT value rather than
    silently falling back.
    """

    raw = os.getenv("TRANSPORT", "stdio")
    if raw not in _VALID_TRANSPORTS:
        raise ValueError(
            f"Invalid TRANSPORT {raw!r}. "
            f"Must be one of: {', '.join(_VALID_TRANSPORTS)}."
        )
    transport: Literal["stdio", "sse", "streamable-http"] = raw
    port = int(os.getenv("PORT", "8765"))
    server = create_server(port=port)
    server.run(transport=transport)


if __name__ == "__main__":
    main()
