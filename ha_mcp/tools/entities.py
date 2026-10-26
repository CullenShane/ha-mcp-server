"""MCP tools for Home Assistant entity and service management."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ha_mcp.client import HomeAssistantError
from ha_mcp.tools.gating import DEFAULT_FLAGS, ToolKind, make_registrar

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from ha_mcp.client import HomeAssistantClient
    from ha_mcp.config import FeatureFlags

# Jinja2 template that returns every entity→area mapping as a JSON list.
# Used by both list_devices and list_entity_registry.
_AREA_ENTITIES_TEMPLATE = (
    "{%- set ns = namespace(entities=[]) -%}"
    "{%- for area_id in areas() -%}"
    "{%- for entity_id in area_entities(area_id) -%}"
    "{%- set ns.entities = ns.entities + [{"
    "'entity_id': entity_id,"
    "'area_id': area_id,"
    "'area_name': area_name(area_id)"
    "}] -%}"
    "{%- endfor -%}"
    "{%- endfor -%}"
    "{{ ns.entities | tojson }}"
)


def _parse_template_json(result: Any) -> list[dict[str, Any]]:
    """
    Normalise a /api/template response into a list of dicts.

    HA may return either a pre-parsed list or a JSON-encoded string depending
    on how the template is rendered. Wrapping the decode here keeps the call
    sites readable and converts malformed JSON into a HomeAssistantError so
    callers get a consistent failure type.

    Args:
        result: Either a list (already parsed) or a JSON-encoded string.

    Returns:
        The parsed list of dicts.

    Raises:
        HomeAssistantError: If result is a string that is not valid JSON.
    """

    if isinstance(result, list):
        return result
    try:
        return json.loads(result)
    except (json.JSONDecodeError, TypeError) as exc:
        raise HomeAssistantError(
            f"Template returned malformed JSON: {result!r}"
        ) from exc


def register(mcp: FastMCP, flags: FeatureFlags = DEFAULT_FLAGS) -> None:
    """Register all entity and service tools on the MCP server."""

    tool = make_registrar(mcp, flags)

    @tool(ToolKind.CORE_READ, annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    async def list_entities(
        ctx: Context,
        domain: str | None = None,
        instance: str = "",
    ) -> list[dict[str, Any]]:
        """
        List all Home Assistant entities, optionally filtered by domain.

        Returns raw state objects from the HA state machine. Each object
        includes the full attributes dict, which may contain friendly_name,
        unit of measurement, device class, and other domain-specific metadata.
        When domain is provided only entities whose entity_id starts with
        <domain>. are returned.

        Args:
            ctx: MCP request context (injected by FastMCP).
            domain: Optional domain filter, e.g. light, switch, sensor.
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            A list of entity state objects with entity_id, state, and attributes.
        """

        state = ctx.request_context.lifespan_context
        client: HomeAssistantClient = state.clients[instance or state.default_instance]
        states: list[dict[str, Any]] = await client.get("/api/states")

        if domain is None:
            return states

        return [s for s in states if s["entity_id"].startswith(f"{domain}.")]

    @tool(ToolKind.CORE_READ, annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    async def get_entity(
        ctx: Context,
        entity_id: str,
        instance: str = "",
    ) -> dict[str, Any]:
        """
        Get the current state and attributes of a single entity.

        Fetches the live state directly from the HA state machine.

        Args:
            ctx: MCP request context (injected by FastMCP).
            entity_id: Full entity ID, e.g. light.living_room.
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            Entity state object with entity_id, state,
            attributes, and timestamps.
        """

        state = ctx.request_context.lifespan_context
        client: HomeAssistantClient = state.clients[instance or state.default_instance]
        return await client.get(f"/api/states/{entity_id}")

    @tool(ToolKind.CORE_WRITE, annotations=ToolAnnotations(openWorldHint=True))
    async def set_entity_state(
        ctx: Context,
        entity_id: str,
        state: str,
        attributes: dict[str, Any] | None = None,
        instance: str = "",
    ) -> dict[str, Any]:
        """
        Directly set the state and attributes of an entity in the HA state machine.

        This is a low-level write to the state machine and does **not** send a
        command to the underlying device. For physical devices (lights,
        switches, thermostats, etc.) use call_service instead. For input
        helpers prefer the dedicated set_input_boolean, set_input_number, and
        related tools over this one. This tool is primarily useful for writing
        arbitrary state to virtual entities that have no dedicated service.

        Args:
            ctx: MCP request context (injected by FastMCP).
            entity_id: Full entity ID, e.g. input_boolean.vacation_mode.
            state: New state string, e.g. on, off, home.
            attributes: Optional dictionary of attributes to set alongside the
                        state.
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            The updated entity state object.
        """

        lifespan = ctx.request_context.lifespan_context
        client: HomeAssistantClient = lifespan.clients[instance or lifespan.default_instance]
        return await client.post(
            f"/api/states/{entity_id}",
            {"state": state, "attributes": attributes or {}},
        )

    @tool(ToolKind.CORE_WRITE, annotations=ToolAnnotations(openWorldHint=True))
    async def call_service(
        ctx: Context,
        domain: str,
        service: str,
        service_data: dict[str, Any] | None = None,
        instance: str = "",
    ) -> list[dict[str, Any]]:
        """
        Call a Home Assistant service.

        This is the primary way to control physical devices. Services are the
        correct mechanism for turning devices on/off, adjusting brightness,
        setting thermostat temperatures, running scripts, triggering
        automations, and so on. Use list_services to discover available
        domain/service combinations and their accepted parameters.

        Args:
            ctx: MCP request context (injected by FastMCP).
            domain: Service domain, e.g. light, switch, climate, script.
            service: Service name, e.g. turn_on, turn_off, toggle.
            service_data: Optional data payload, e.g.
                          {"entity_id": "light.kitchen", "brightness": 200}.
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            List of entity states affected by the service call.
        """

        lifespan = ctx.request_context.lifespan_context
        client: HomeAssistantClient = lifespan.clients[instance or lifespan.default_instance]
        return await client.post(
            f"/api/services/{domain}/{service}",
            service_data or {},
        )

    @tool(ToolKind.CORE_READ, annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    async def search_entities(
        ctx: Context,
        query: str,
        instance: str = "",
    ) -> list[dict[str, Any]]:
        """
        Search for entities by ID, friendly name, or state.

        The match is case-insensitive and checks all three fields. An entity is
        included if the query appears in any one of them. Entities that have no
        friendly_name attribute are still searchable via their entity_id and
        state.

        Args:
            ctx: MCP request context (injected by FastMCP).
            query: Case-insensitive search string.
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            Matching entity state objects.
        """

        lifespan = ctx.request_context.lifespan_context
        client: HomeAssistantClient = lifespan.clients[instance or lifespan.default_instance]
        states: list[dict[str, Any]] = await client.get("/api/states")

        query_lower = query.lower()
        results = []
        for entity in states:
            entity_id: str = entity.get("entity_id", "")
            friendly_name: str = entity.get("attributes", {}).get("friendly_name", "")
            entity_state: str = entity.get("state", "")

            if any(
                query_lower in field.lower()
                for field in [entity_id, friendly_name, entity_state]
            ):
                results.append(entity)

        return results

    @tool(ToolKind.CORE_READ, annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    async def list_services(
        ctx: Context,
        instance: str = "",
    ) -> list[dict[str, Any]]:
        """
        List all available Home Assistant services grouped by domain.

        Useful for discovering what domain and service values to pass to
        call_service, and what parameters each service accepts.

        Args:
            ctx: MCP request context (injected by FastMCP).
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            List of service group objects, each with a domain key and a
            services dict mapping service names to their parameter schemas.
        """

        lifespan = ctx.request_context.lifespan_context
        client: HomeAssistantClient = lifespan.clients[instance or lifespan.default_instance]
        return await client.get("/api/services")

    @tool(ToolKind.CORE_READ, annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    async def list_areas(
        ctx: Context,
        instance: str = "",
    ) -> list[dict[str, Any]]:
        """
        List all configured areas in Home Assistant.

        Areas are logical groupings of devices and entities (e.g. "Living Room",
        "Kitchen"). The returned area_id values can be used with
        list_entity_registry to filter entities by area.

        Args:
            ctx: MCP request context (injected by FastMCP).
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            List of area objects with area_id and name.
        """

        template = (
            "{%- set ns = namespace(areas=[]) -%}"
            "{%- for area_id in areas() -%}"
            "{%- set ns.areas = ns.areas"
            " + [{'area_id': area_id, 'name': area_name(area_id)}] -%}"
            "{%- endfor -%}"
            "{{ ns.areas | tojson }}"
        )

        lifespan = ctx.request_context.lifespan_context
        client: HomeAssistantClient = lifespan.clients[instance or lifespan.default_instance]
        result = await client.post("/api/template", {"template": template})
        return _parse_template_json(result)

    @tool(ToolKind.CORE_READ, annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    async def list_devices(
        ctx: Context,
        instance: str = "",
    ) -> list[dict[str, Any]]:
        """
        List all entities with their friendly names and area assignments.

        Combines live state data (for friendly names and current state) with
        the HA template engine (for area assignments). Every entity in the
        state machine is returned regardless of whether it belongs to an area.
        Entities without a configured friendly name fall back to their
        entity_id. Entities not assigned to any area will have area_id and
        area_name set to null.

        Args:
            ctx: MCP request context (injected by FastMCP).
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            List of objects with entity_id, friendly_name, state, area_id, and
            area_name.
        """

        lifespan = ctx.request_context.lifespan_context
        client: HomeAssistantClient = lifespan.clients[instance or lifespan.default_instance]
        area_result = await client.post(
            "/api/template", {"template": _AREA_ENTITIES_TEMPLATE}
        )
        states: list[dict[str, Any]] = await client.get("/api/states")

        area_entries = _parse_template_json(area_result)
        area_map = {entry["entity_id"]: entry for entry in area_entries}

        return [
            {
                "entity_id": state["entity_id"],
                "friendly_name": state.get("attributes", {}).get(
                    "friendly_name", state["entity_id"]
                ),
                "state": state.get("state"),
                "area_id": area_map.get(state["entity_id"], {}).get("area_id"),
                "area_name": area_map.get(state["entity_id"], {}).get("area_name"),
            }
            for state in states
        ]

    @tool(ToolKind.CORE_READ, annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    async def list_entity_registry(
        ctx: Context,
        instance: str = "",
    ) -> list[dict[str, Any]]:
        """
        List area-assigned entities with friendly names and current state.

        Unlike list_devices, this tool returns **only** entities that have an
        area assignment, which is useful for queries scoped to a room or zone.
        Friendly names are sourced from live state. Entities without a
        configured friendly name fall back to their entity_id.

        Args:
            ctx: MCP request context (injected by FastMCP).
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            List of objects with entity_id, friendly_name, state, area_id, and
            area_name.
        """

        lifespan = ctx.request_context.lifespan_context
        client: HomeAssistantClient = lifespan.clients[instance or lifespan.default_instance]
        area_result = await client.post(
            "/api/template", {"template": _AREA_ENTITIES_TEMPLATE}
        )
        states: list[dict[str, Any]] = await client.get("/api/states")

        area_entries = _parse_template_json(area_result)
        state_map = {s["entity_id"]: s for s in states}

        return [
            {
                "entity_id": entry["entity_id"],
                "friendly_name": state_map.get(entry["entity_id"], {})
                .get("attributes", {})
                .get("friendly_name", entry["entity_id"]),
                "state": state_map.get(entry["entity_id"], {}).get("state"),
                "area_id": entry["area_id"],
                "area_name": entry["area_name"],
            }
            for entry in area_entries
        ]

    @tool(ToolKind.CORE_READ, annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    async def get_entity_history(
        ctx: Context,
        entity_id: str,
        start_time: str | None = None,
        end_time: str | None = None,
        instance: str = "",
    ) -> list[list[dict[str, Any]]]:
        """
        Retrieve the historical state changes for an entity.

        Queries the HA history API. When start_time is omitted, HA defaults to
        the past 24 hours. Each inner list in the response corresponds to one
        entity (only one entity is requested here, so the outer list will
        normally contain a single element).

        Args:
            ctx: MCP request context (injected by FastMCP).
            entity_id: Full entity ID, e.g. sensor.temperature.
            start_time: ISO 8601 timestamp for the start of the range, e.g.
                        2024-01-01T00:00:00.
            end_time: ISO 8601 timestamp for the end of the range.
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            List of lists of historical state objects, one inner list per
            entity.
        """

        path = "/api/history/period"
        if start_time:
            path = f"{path}/{start_time}"

        params: dict[str, str] = {"filter_entity_id": entity_id}
        if end_time:
            params["end_time"] = end_time

        lifespan = ctx.request_context.lifespan_context
        client: HomeAssistantClient = lifespan.clients[instance or lifespan.default_instance]
        return await client.get(path, params=params)

    @tool(ToolKind.CORE_READ, annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    async def get_logbook(
        ctx: Context,
        entity_id: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        instance: str = "",
    ) -> list[dict[str, Any]]:
        """
        Fetch logbook entries, optionally filtered by entity and time range.

        The logbook records human-readable events such as state changes,
        service calls, and automation triggers. When no filters are provided,
        HA returns entries for the past 24 hours across all entities. Filtering
        by entity_id narrows results to events involving that specific entity.

        Args:
            ctx: MCP request context (injected by FastMCP).
            entity_id: Optional entity ID to filter entries.
            start_time: ISO 8601 start timestamp.
            end_time: ISO 8601 end timestamp.
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            List of logbook entry objects.
        """

        path = "/api/logbook"
        if start_time:
            path = f"{path}/{start_time}"

        params: dict[str, str] = {}
        if entity_id:
            params["entity"] = entity_id
        if end_time:
            params["end_time"] = end_time

        lifespan = ctx.request_context.lifespan_context
        client: HomeAssistantClient = lifespan.clients[instance or lifespan.default_instance]
        return await client.get(path, params=params or None)

    @tool(ToolKind.CORE_READ, annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    async def render_template(
        ctx: Context,
        template: str,
        instance: str = "",
    ) -> str:
        """
        Render a Jinja2 template string using Home Assistant's template engine.

        Gives access to the full set of HA template functions and filters
        (states(), is_state(), area_entities(), now(), etc.). Useful for
        building dynamic queries or aggregations that aren't directly exposed
        by other tools.

        Args:
            ctx: MCP request context (injected by FastMCP).
            template: A Jinja2 template string,
                      e.g. {{ states('sensor.temperature') }}.
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            The rendered string result.
        """

        lifespan = ctx.request_context.lifespan_context
        client: HomeAssistantClient = lifespan.clients[instance or lifespan.default_instance]
        return await client.post("/api/template", {"template": template})

    @tool(ToolKind.CORE_WRITE, annotations=ToolAnnotations(openWorldHint=True))
    async def fire_event(
        ctx: Context,
        event_type: str,
        event_data: dict[str, Any] | None = None,
        instance: str = "",
    ) -> dict[str, Any]:
        """
        Fire a custom event on the Home Assistant event bus.

        Any automation or integration listening for event_type will be
        triggered. This is an advanced tool intended for custom integrations
        and automations that respond to named events. Most device control
        should go through call_service instead.

        Args:
            ctx: MCP request context (injected by FastMCP).
            event_type: Name of the event to fire, e.g. my_custom_event.
            event_data: Optional dictionary of data to include with the event.
            instance: HA instance name from the config file. Uses the default
                      instance if omitted.

        Returns:
            Confirmation message from HA.
        """

        lifespan = ctx.request_context.lifespan_context
        client: HomeAssistantClient = lifespan.clients[instance or lifespan.default_instance]
        return await client.post(f"/api/events/{event_type}", event_data or {})
