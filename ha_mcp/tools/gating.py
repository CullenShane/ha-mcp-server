"""
Feature gating for MCP tool registration.

The fork runs Home Assistant as a Container (plain Docker, no Supervisor) and is
read-only by default. Every tool module classifies each of its tools with a
:class:`ToolKind`, and registration is decided centrally from the
:class:`~ha_mcp.config.FeatureFlags` so that the tool surface shrinks by
default and only widens on explicit opt-in.

Registration rules:

- ``CORE_READ``: always registered.
- ``CORE_WRITE``: registered only when ``HA_READONLY=false``.
- ``RESTART``: registered only when ``HA_ENABLE_RESTART=true`` **and**
  ``HA_READONLY=false``.
- ``SUPERVISOR_READ``: registered only when ``HA_ENABLE_SUPERVISOR=true``.
- ``SUPERVISOR_WRITE``: registered only when ``HA_ENABLE_SUPERVISOR=true``
  **and** ``HA_READONLY=false``.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Any

from ha_mcp.config import FeatureFlags

if TYPE_CHECKING:
    from collections.abc import Callable

    from mcp.server.fastmcp import FastMCP

    ToolFunction = Callable[..., Any]
    ToolDecorator = Callable[[ToolFunction], ToolFunction]
    Registrar = Callable[..., ToolDecorator]


class ToolKind(StrEnum):
    """Classification of a tool for feature gating."""

    CORE_READ = "core_read"
    CORE_WRITE = "core_write"
    RESTART = "restart"
    SUPERVISOR_READ = "supervisor_read"
    SUPERVISOR_WRITE = "supervisor_write"


# Permissive default used by the ``register(mcp)`` signature so that unit tests
# that register a module with only a capture object see every tool. Production
# always passes explicit flags derived from the environment.
DEFAULT_FLAGS = FeatureFlags(
    readonly=False,
    enable_restart=True,
    enable_supervisor=True,
)


def allowed(kind: ToolKind, flags: FeatureFlags) -> bool:
    """
    Return whether a tool of ``kind`` should be registered for ``flags``.

    Args:
        kind: The tool's classification.
        flags: The active feature flags.

    Returns:
        True if the tool should be registered, False to skip it.

    Raises:
        ValueError: If ``kind`` is not a recognised ToolKind.
    """

    if kind is ToolKind.CORE_READ:
        return True
    if kind is ToolKind.CORE_WRITE:
        return not flags.readonly
    if kind is ToolKind.RESTART:
        return flags.enable_restart and not flags.readonly
    if kind is ToolKind.SUPERVISOR_READ:
        return flags.enable_supervisor
    if kind is ToolKind.SUPERVISOR_WRITE:
        return flags.enable_supervisor and not flags.readonly
    raise ValueError(f"Unknown ToolKind: {kind!r}")


def make_registrar(mcp: FastMCP, flags: FeatureFlags) -> Registrar:
    """
    Build a gated ``@tool(kind, **tool_kwargs)`` decorator bound to ``flags``.

    The returned registrar mirrors ``mcp.tool``'s keyword interface (e.g.
    ``annotations=...``) and additionally takes a :class:`ToolKind` that decides
    whether the decorated function is registered at all. Tools that are not
    allowed by the current flags are returned unregistered.

    Args:
        mcp: The FastMCP server (or test capture) to register tools on.
        flags: The active feature flags.

    Returns:
        A registrar callable for use as ``@tool(ToolKind.X, ...)``.
    """

    def registrar(kind: ToolKind, **tool_kwargs: Any) -> ToolDecorator:
        def decorator(fn: ToolFunction) -> ToolFunction:
            if allowed(kind, flags):
                mcp.tool(**tool_kwargs)(fn)
            return fn

        return decorator

    return registrar
