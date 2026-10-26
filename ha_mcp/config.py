"""Configuration loading for multiple Home Assistant instances."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
import yaml


@dataclass
class InstanceConfig:
    """Connection details for a single Home Assistant instance."""

    name: str
    url: str
    token: str


@dataclass
class FeatureFlags:
    """Feature gates controlling which tools the server registers."""

    readonly: bool = True
    enable_restart: bool = False
    enable_supervisor: bool = False


@dataclass
class AppConfig:
    """Resolved configuration for all Home Assistant instances."""

    instances: list[InstanceConfig]
    default: str


_TRUTHY = frozenset({"1", "true", "yes", "on"})


def _env_bool(name: str, default: bool) -> bool:
    """
    Read a boolean feature flag from the environment.

    Args:
        name: Environment variable name.
        default: Value returned when the variable is unset.

    Returns:
        True when the variable is set to a truthy token (1, true, yes, on;
        case-insensitive), the ``default`` when unset, otherwise False.
    """

    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in _TRUTHY


def load_flags() -> FeatureFlags:
    """
    Resolve feature gates from the environment.

    Reads HA_READONLY (default true), HA_ENABLE_RESTART (default false) and
    HA_ENABLE_SUPERVISOR (default false). Read-only is the default: the server
    registers no write/destructive tools unless HA_READONLY is explicitly set to
    a falsy value. Supervisor tools are never registered unless
    HA_ENABLE_SUPERVISOR is explicitly true.

    Returns:
        A FeatureFlags instance reflecting the current environment.
    """

    return FeatureFlags(
        readonly=_env_bool("HA_READONLY", True),
        enable_restart=_env_bool("HA_ENABLE_RESTART", False),
        enable_supervisor=_env_bool("HA_ENABLE_SUPERVISOR", False),
    )


def load_config() -> AppConfig:
    """
    Load instance configuration from a YAML/JSON file or environment variables.

    Resolution order:
    1. File at the path given by the HA_CONFIG environment variable.
    2. ha-mcp.yaml or ha-mcp.yml or ha-mcp.json in the current directory.
    3. HA_URL + HA_TOKEN environment variables (with .env fallback), producing
       a single instance named "default".

    Returns:
        AppConfig with at least one instance and a default instance name.

    Raises:
        FileNotFoundError: If HA_CONFIG points to a non-existent file.
        ValueError: If the config file is missing required fields, or if no
                    config source is found.
    """

    config_path_env = os.getenv("HA_CONFIG")
    if config_path_env:
        return _load_from_file(Path(config_path_env))

    for candidate in (Path("ha-mcp.yaml"), Path("ha-mcp.yml"), Path("ha-mcp.json")):
        if candidate.exists():
            return _load_from_file(candidate)

    load_dotenv(Path(__file__).parent.parent / ".env")
    ha_url = os.getenv("HA_URL")
    ha_token = os.getenv("HA_TOKEN")

    if not ha_url:
        raise ValueError(
            "No config file found and HA_URL is not set. "
            "Create ha-mcp.yaml or set HA_URL and HA_TOKEN."
        )
    if not ha_token:
        raise ValueError(
            "No config file found and HA_TOKEN is not set. "
            "Create ha-mcp.yaml or set HA_URL and HA_TOKEN."
        )

    return AppConfig(
        instances=[InstanceConfig(name="default", url=ha_url, token=ha_token)],
        default="default",
    )


def _load_from_file(path: Path) -> AppConfig:
    """
    Parse a YAML or JSON config file and return an AppConfig.

    Args:
        path: Path to the config file. Extension determines the parser used:
              .yaml/.yml → PyYAML, anything else → JSON.

    Returns:
        Parsed AppConfig.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the instances list is absent or empty.
    """

    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    raw = path.read_text(encoding="utf-8")
    data: dict[str, Any] = (
        yaml.safe_load(raw) if path.suffix in {".yaml", ".yml"} else json.loads(raw)
    )

    raw_instances: list[dict[str, Any]] = data.get("instances", [])
    if not raw_instances:
        raise ValueError(
            f"Config file {path} must contain at least one entry under 'instances'."
        )

    instances = [
        InstanceConfig(name=i["name"], url=i["url"], token=i["token"])
        for i in raw_instances
    ]
    return AppConfig(
        instances=instances, default=data.get("default", instances[0].name)
    )
