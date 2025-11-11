"""Configuration helpers for preprocessing routines."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml

CONFIG_PATH = Path(__file__).resolve().parents[2] / "configs" / "preprocessing.yaml"


@dataclass(slots=True)
class BackgroundParameter:
    """Parameter description for a preprocessing method."""

    name: str
    label: str
    type: str
    default: Any | None = None
    minimum: float | None = None
    maximum: float | None = None
    choices: list[Any] | None = None
    description: str | None = None


@dataclass(slots=True)
class BackgroundMethod:
    """Available background processing routine."""

    name: str
    label: str
    description: str | None
    parameters: list[BackgroundParameter]


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Preprocessing config not found at {path}")
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _as_parameter(payload: dict[str, Any]) -> BackgroundParameter:
    return BackgroundParameter(
        name=payload["name"],
        label=payload.get("label", payload["name"].replace("_", " ").title()),
        type=payload.get("type", "number"),
        default=payload.get("default"),
        minimum=payload.get("minimum"),
        maximum=payload.get("maximum"),
        choices=payload.get("choices"),
        description=payload.get("description"),
    )


def _as_method(payload: dict[str, Any]) -> BackgroundMethod:
    params = [_as_parameter(item) for item in payload.get("parameters", [])]
    return BackgroundMethod(
        name=payload["name"],
        label=payload.get("label", payload["name"].title()),
        description=payload.get("description"),
        parameters=params,
    )


def load_background_configs(path: Path | None = None) -> list[BackgroundMethod]:
    """Load the available background preprocessing definitions."""

    config_path = path or CONFIG_PATH
    if not config_path.exists():
        # Provide a minimal fallback configuration to keep the API responsive
        return [
            BackgroundMethod(
                name="basic",
                label="BaSiC",
                description="Rolling-ball background estimation.",
                parameters=[
                    BackgroundParameter(
                        name="rolling_ball_radius",
                        label="Rolling Ball Radius",
                        type="number",
                        default=50,
                        minimum=5,
                        maximum=200,
                        description="Radius of the rolling ball used for background estimation.",
                    )
                ],
            )
        ]
    payload = _load_yaml(config_path)
    methods: Iterable[dict[str, Any]] = payload.get("background", {}).get("methods", [])
    return [_as_method(item) for item in methods]


__all__ = ["BackgroundParameter", "BackgroundMethod", "load_background_configs"]
