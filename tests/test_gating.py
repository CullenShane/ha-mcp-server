"""Unit tests for the tool feature-gating rules."""

from __future__ import annotations

import pytest

from ha_mcp.config import FeatureFlags
from ha_mcp.tools.gating import ToolKind, allowed, make_registrar


@pytest.mark.parametrize(
    ("kind", "flags", "expected"),
    [
        (ToolKind.CORE_READ, FeatureFlags(), True),
        (ToolKind.CORE_READ, FeatureFlags(readonly=True), True),
        (ToolKind.CORE_WRITE, FeatureFlags(readonly=True), False),
        (ToolKind.CORE_WRITE, FeatureFlags(readonly=False), True),
        (ToolKind.RESTART, FeatureFlags(readonly=False), False),
        (
            ToolKind.RESTART,
            FeatureFlags(readonly=False, enable_restart=True),
            True,
        ),
        (ToolKind.RESTART, FeatureFlags(readonly=True, enable_restart=True), False),
        (ToolKind.HASSIO_READ, FeatureFlags(), False),
        (ToolKind.HASSIO_READ, FeatureFlags(enable_hassio=True), True),
        (ToolKind.HASSIO_WRITE, FeatureFlags(enable_hassio=True), False),
        (
            ToolKind.HASSIO_WRITE,
            FeatureFlags(readonly=False, enable_hassio=True),
            True,
        ),
    ],
)
def test_allowed(kind: ToolKind, flags: FeatureFlags, expected: bool) -> None:
    """allowed() applies the documented gate rules for each ToolKind."""

    assert allowed(kind, flags) is expected


def test_allowed_rejects_unknown_kind() -> None:
    """allowed() raises ValueError for an unrecognised kind value."""

    with pytest.raises(ValueError, match="Unknown ToolKind"):
        allowed("not_a_kind", FeatureFlags())  # type: ignore[arg-type]


def test_make_registrar_skips_disallowed_tool() -> None:
    """A write tool is not registered when read-only is active."""

    registered: dict[str, object] = {}

    def _decorator(fn: object) -> object:
        registered[getattr(fn, "__name__", "?")] = fn
        return fn

    class _Capture:
        def tool(self, **_kwargs: object) -> object:
            return _decorator

    registrar = make_registrar(_Capture(), FeatureFlags(readonly=True))  # type: ignore[arg-type]

    @registrar(ToolKind.CORE_WRITE, annotations=None)
    def a_write_tool() -> None:
        return None

    @registrar(ToolKind.CORE_READ, annotations=None)
    def a_read_tool() -> None:
        return None

    assert "a_read_tool" in registered
    assert "a_write_tool" not in registered
