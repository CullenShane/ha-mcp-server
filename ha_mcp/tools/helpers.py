"""
MCP tools for Home Assistant input helpers and timers.

Covers the input_boolean, input_number, input_select, input_text,
input_datetime, and timer domains.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ha_mcp.tools.gating import DEFAULT_FLAGS, ToolKind, make_registrar

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from ha_mcp.client import HomeAssistantClient
    from ha_mcp.config import FeatureFlags

_HELPER_DOMAINS = frozenset(
    {
        "input_boolean",
        "input_datetime",
        "input_number",
        "input_select",
        "input_text",
        "timer",
    }
)


def register(mcp: FastMCP, flags: FeatureFlags = DEFAULT_FLAGS) -> None:
    """Register all input helper and timer tools on the MCP server."""

    tool = make_registrar(mcp, flags)

    @tool(ToolKind.CORE_READ, annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    async def list_input_helpers(
        ctx: Context,
        domain: str | None = None,
        instance: str = "",
    ) -> list[dict[str, Any]]:
        """
        List Home Assistant input helper and timer entities.

        Returns entities from the virtual-device domains: input_boolean,
        input_button, input_datetime, input_number, input_select, input_text,
        and timer. When domain is provided only entities of that specific type
        are returned.

        Args:
            ctx: MCP request context (injected by FastMCP).
            domain: Optional domain filter, e.g. input_boolean or timer.
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            List of entity state objects for the matching helper domains.
        """

        lifespan = ctx.request_context.lifespan_context
        client: HomeAssistantClient = lifespan.clients[instance or lifespan.default_instance]
        states: list[dict[str, Any]] = await client.get("/api/states")

        if domain is not None:
            return [s for s in states if s["entity_id"].startswith(f"{domain}.")]

        return [s for s in states if s["entity_id"].split(".")[0] in _HELPER_DOMAINS]

    @tool(ToolKind.CORE_WRITE, annotations=ToolAnnotations(openWorldHint=True))
    async def set_input_boolean(
        ctx: Context,
        entity_id: str,
        state: str,
        instance: str = "",
    ) -> list[dict[str, Any]]:
        """
        Turn an input_boolean helper on or off.

        Args:
            ctx: MCP request context (injected by FastMCP).
            entity_id: Input boolean entity ID, e.g.
                       input_boolean.vacation_mode.
            state: Target state. Must be "on" or "off".
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            List of affected entity states.

        Raises:
            ValueError: If state is not "on" or "off".
        """

        if state not in ("on", "off"):
            raise ValueError(f"state must be 'on' or 'off', got {state!r}")

        service = "turn_on" if state == "on" else "turn_off"
        lifespan = ctx.request_context.lifespan_context
        client: HomeAssistantClient = lifespan.clients[instance or lifespan.default_instance]
        return await client.post(
            f"/api/services/input_boolean/{service}",
            {"entity_id": entity_id},
        )

    @tool(ToolKind.CORE_WRITE, annotations=ToolAnnotations(openWorldHint=True))
    async def set_input_number(
        ctx: Context,
        entity_id: str,
        value: float,
        instance: str = "",
    ) -> list[dict[str, Any]]:
        """
        Set the numeric value of an input_number helper.

        The value must be within the min/max range configured for the entity.
        Use get_entity to inspect the min, max, and step attributes before
        calling this. HA enforces the range server-side and will return an
        error if the value is out of bounds.

        Args:
            ctx: MCP request context (injected by FastMCP).
            entity_id: Input number entity ID, e.g. input_number.target_temp.
            value: New numeric value. Must be finite (not NaN or infinity).
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            List of affected entity states.

        Raises:
            ValueError: If value is NaN or infinity.
        """

        if not math.isfinite(value):
            raise ValueError(f"value must be a finite number, got {value!r}")

        lifespan = ctx.request_context.lifespan_context
        client: HomeAssistantClient = lifespan.clients[instance or lifespan.default_instance]
        return await client.post(
            "/api/services/input_number/set_value",
            {"entity_id": entity_id, "value": value},
        )

    @tool(ToolKind.CORE_WRITE, annotations=ToolAnnotations(openWorldHint=True))
    async def set_input_select(
        ctx: Context,
        entity_id: str,
        option: str,
        instance: str = "",
    ) -> list[dict[str, Any]]:
        """
        Select an option on an input_select helper.

        The option must exactly match one of the values listed in the entity's
        options attribute (case-sensitive). Use get_entity to retrieve the
        available options first. HA will return an error if the option does
        not exist in the configured list.

        Args:
            ctx: MCP request context (injected by FastMCP).
            entity_id: Input select entity ID, e.g. input_select.preset_mode.
            option: Option string to select, e.g. "Away".
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            List of affected entity states.

        Raises:
            ValueError: If option is an empty string.
        """

        if not option:
            raise ValueError("option must not be empty")

        lifespan = ctx.request_context.lifespan_context
        client: HomeAssistantClient = lifespan.clients[instance or lifespan.default_instance]
        return await client.post(
            "/api/services/input_select/select_option",
            {"entity_id": entity_id, "option": option},
        )

    @tool(ToolKind.CORE_WRITE, annotations=ToolAnnotations(openWorldHint=True))
    async def set_input_text(
        ctx: Context,
        entity_id: str,
        value: str,
        instance: str = "",
    ) -> list[dict[str, Any]]:
        """
        Set the text value of an input_text helper.

        The value must satisfy the min/max length and optional pattern
        constraints configured for the entity. HA enforces these server-side.

        Args:
            ctx: MCP request context (injected by FastMCP).
            entity_id: Input text entity ID,
                       e.g. input_text.welcome_message.
            value: New text value.
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            List of affected entity states.
        """

        lifespan = ctx.request_context.lifespan_context
        client: HomeAssistantClient = lifespan.clients[instance or lifespan.default_instance]
        return await client.post(
            "/api/services/input_text/set_value",
            {"entity_id": entity_id, "value": value},
        )

    @tool(ToolKind.CORE_WRITE, annotations=ToolAnnotations(openWorldHint=True))
    async def set_input_datetime(
        ctx: Context,
        entity_id: str,
        date: str | None = None,
        time: str | None = None,
        datetime_str: str | None = None,
        instance: str = "",
    ) -> list[dict[str, Any]]:
        """
        Set the value of an input_datetime helper.

        Supply whichever of date, time, or datetime_str matches the entity's
        configured mode: date for date-only, time for time-only, datetime_str
        for combined date+time. Check the entity's has_date and has_time
        attributes via get_entity to determine the mode. Passing a field the
        entity does not support will be silently ignored by Home Assistant.

        Args:
            ctx: MCP request context (injected by FastMCP).
            entity_id: Input datetime entity ID, e.g. input_datetime.alarm_time.
            date: Date string in YYYY-MM-DD format.
            time: Time string in HH:MM:SS format.
            datetime_str: Combined datetime in YYYY-MM-DD HH:MM:SS format.
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            List of affected entity states.

        Raises:
            ValueError: If none of date, time, or datetime_str is provided.
        """

        if date is None and time is None and datetime_str is None:
            raise ValueError(
                "At least one of date, time, or datetime_str must be provided."
            )

        payload: dict[str, Any] = {"entity_id": entity_id}
        if date is not None:
            payload["date"] = date
        if time is not None:
            payload["time"] = time
        if datetime_str is not None:
            payload["datetime"] = datetime_str

        lifespan = ctx.request_context.lifespan_context
        client: HomeAssistantClient = lifespan.clients[instance or lifespan.default_instance]
        return await client.post(
            "/api/services/input_datetime/set_datetime", payload
        )

    @tool(ToolKind.CORE_WRITE, annotations=ToolAnnotations(openWorldHint=True))
    async def start_timer(
        ctx: Context,
        entity_id: str,
        duration: str | None = None,
        instance: str = "",
    ) -> list[dict[str, Any]]:
        """
        Start or restart a timer entity.

        If duration is omitted the timer uses its configured default
        duration. Calling start on an already-running timer restarts it.

        Args:
            ctx: MCP request context (injected by FastMCP).
            entity_id: Timer entity ID, e.g. timer.cooking.
            duration: Optional override duration in HH:MM:SS or SS format, e.g.
                      "00:05:00" for five minutes.
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            List of affected entity states.
        """

        payload: dict[str, Any] = {"entity_id": entity_id}
        if duration is not None:
            payload["duration"] = duration

        lifespan = ctx.request_context.lifespan_context
        client: HomeAssistantClient = lifespan.clients[instance or lifespan.default_instance]
        return await client.post("/api/services/timer/start", payload)

    @tool(ToolKind.CORE_WRITE, annotations=ToolAnnotations(openWorldHint=True))
    async def pause_timer(
        ctx: Context,
        entity_id: str,
        instance: str = "",
    ) -> list[dict[str, Any]]:
        """
        Pause a running timer entity.

        The remaining time is preserved. Use start_timer to resume.

        Args:
            ctx: MCP request context (injected by FastMCP).
            entity_id: Timer entity ID, e.g. timer.cooking.
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            List of affected entity states.
        """

        lifespan = ctx.request_context.lifespan_context
        client: HomeAssistantClient = lifespan.clients[instance or lifespan.default_instance]
        return await client.post(
            "/api/services/timer/pause", {"entity_id": entity_id}
        )

    @tool(ToolKind.CORE_WRITE, annotations=ToolAnnotations(openWorldHint=True))
    async def cancel_timer(
        ctx: Context,
        entity_id: str,
        instance: str = "",
    ) -> list[dict[str, Any]]:
        """
        Cancel a running or paused timer entity.

        The timer is reset to its configured duration. No timer.finished event
        is fired.

        Args:
            ctx: MCP request context (injected by FastMCP).
            entity_id: Timer entity ID, e.g. timer.cooking.
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            List of affected entity states.
        """

        lifespan = ctx.request_context.lifespan_context
        client: HomeAssistantClient = lifespan.clients[instance or lifespan.default_instance]
        return await client.post(
            "/api/services/timer/cancel", {"entity_id": entity_id}
        )
