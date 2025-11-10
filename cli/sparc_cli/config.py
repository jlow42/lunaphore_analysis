"""Configuration loading utilities for the Sparc CLI."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml


@dataclass(slots=True)
class RunConfig:
    """Configuration for a Sparc analysis job."""

    payload: Mapping[str, Any]


def load_config(config_path: str | Path) -> RunConfig:
    """Load a configuration file in JSON or YAML format.

    Args:
        config_path: Path to the configuration file.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file cannot be parsed.

    Returns:
        RunConfig: The parsed configuration payload.
    """

    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover - filesystem errors are rare
        raise ValueError(f"Failed to read configuration file: {path}") from exc

    suffix = path.suffix.lower()
    if suffix in {".yaml", ".yml"}:
        data = yaml.safe_load(text) or {}
    elif suffix == ".json":
        data = json.loads(text)
    else:
        raise ValueError(
            f"Unsupported configuration format; expected JSON or YAML: {path}"
        )

    if not isinstance(data, Mapping):
        raise ValueError("Configuration payload must be a mapping of keys to values")

    return RunConfig(payload=data)
