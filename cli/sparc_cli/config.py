"""Configuration loading utilities for the Sparc CLI."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import yaml


@dataclass(slots=True)
class RunConfig:
    """Configuration for a Sparc analysis job."""

    project_slug: str
    run_name: str
    image_path: Path
    convert_to_zarr: bool = False
    panel_csv: Path | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def payload(self) -> dict[str, Any]:
        """Return a serialisable payload suitable for API submission."""

        return {
            "project_slug": self.project_slug,
            "run_name": self.run_name,
            "image_path": str(self.image_path),
            "convert_to_zarr": self.convert_to_zarr,
            "panel_csv_path": str(self.panel_csv) if self.panel_csv else None,
            "metadata": dict(self.metadata),
        }

    def input_paths(self) -> list[Path]:
        """Return all paths that should be included in a run snapshot."""

        paths = [self.image_path]
        if self.panel_csv is not None:
            paths.append(self.panel_csv)
        return paths


def load_config(config_path: str | Path) -> RunConfig:
    """Load a configuration file in JSON or YAML format.

    Args:
        config_path: Path to the configuration file.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file cannot be parsed or required keys are missing.

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

    project_slug = _extract_project_slug(data)
    run_name = _extract_run_name(data)
    image_path = _extract_image_path(data)
    panel_csv = _extract_panel_csv(data)
    convert_to_zarr = bool(
        _deep_get(data, ["convert_to_zarr"], False)
        or _deep_get(data, ["options", "convert_to_zarr"], False)
    )
    metadata = _deep_get(data, ["metadata"], {})
    if not isinstance(metadata, Mapping):
        raise ValueError("metadata must be a mapping if provided")

    return RunConfig(
        project_slug=project_slug,
        run_name=run_name,
        image_path=image_path,
        convert_to_zarr=convert_to_zarr,
        panel_csv=panel_csv,
        metadata=metadata,
    )


def _deep_get(data: Mapping[str, Any], keys: list[str], default: Any) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, Mapping) or key not in current:
            return default
        current = current[key]
    return current


def _extract_project_slug(data: Mapping[str, Any]) -> str:
    slug = data.get("project_slug")
    if isinstance(slug, str) and slug.strip():
        return slug.strip()
    project = data.get("project")
    if isinstance(project, Mapping):
        slug = project.get("slug")
        if isinstance(slug, str) and slug.strip():
            return slug.strip()
    raise ValueError("Configuration must define a project slug")


def _extract_run_name(data: Mapping[str, Any]) -> str:
    run_name = data.get("run_name")
    if isinstance(run_name, str) and run_name.strip():
        return run_name.strip()
    run = data.get("run")
    if isinstance(run, Mapping):
        run_name = run.get("name")
        if isinstance(run_name, str) and run_name.strip():
            return run_name.strip()
    raise ValueError("Configuration must define a run name")


def _extract_image_path(data: Mapping[str, Any]) -> Path:
    image = data.get("image_path")
    if isinstance(image, str) and image.strip():
        return Path(image).expanduser()
    inputs = data.get("inputs")
    if isinstance(inputs, Mapping):
        image = inputs.get("image") or inputs.get("ome_tiff")
        if isinstance(image, str) and image.strip():
            return Path(image).expanduser()
    raise ValueError("Configuration must define an image path to ingest")


def _extract_panel_csv(data: Mapping[str, Any]) -> Path | None:
    panel = data.get("panel_csv_path")
    if isinstance(panel, str) and panel.strip():
        return Path(panel).expanduser()
    inputs = data.get("inputs")
    if isinstance(inputs, Mapping):
        panel = inputs.get("panel") or inputs.get("panel_csv")
        if isinstance(panel, str) and panel.strip():
            return Path(panel).expanduser()
    return None


__all__ = ["RunConfig", "load_config"]
