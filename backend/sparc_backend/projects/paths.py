"""Project layout definitions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class ProjectPaths:
    """Filesystem layout for a Sparc project."""

    root: Path

    def ensure(self) -> None:
        """Ensure that all expected directories exist."""

        for path in self.subdirectories().values():
            path.mkdir(parents=True, exist_ok=True)

    def subdirectories(self) -> dict[str, Path]:
        """Return mapping of logical names to subdirectory paths."""

        return {
            "imagery": self.imagery,
            "masks": self.masks,
            "h5ad": self.h5ad,
            "spatialdata": self.spatialdata,
            "configs": self.configs,
            "logs": self.logs,
            "snapshots": self.snapshots,
        }

    @property
    def imagery(self) -> Path:
        return self.root / "imagery"

    @property
    def masks(self) -> Path:
        return self.root / "masks"

    @property
    def h5ad(self) -> Path:
        return self.root / "h5ad"

    @property
    def spatialdata(self) -> Path:
        return self.root / "SpatialData"

    @property
    def configs(self) -> Path:
        return self.root / "configs"

    @property
    def logs(self) -> Path:
        return self.root / "logs"

    @property
    def snapshots(self) -> Path:
        return self.configs / "snapshots"

    def as_dict(self) -> dict[str, str]:
        """Serialize the project layout for API responses."""

        return {name: str(path) for name, path in self.subdirectories().items()}


__all__ = ["ProjectPaths"]
