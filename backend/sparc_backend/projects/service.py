"""Project management utilities."""

from __future__ import annotations

from pathlib import Path

from .paths import ProjectPaths


class ProjectManager:
    """Responsible for creating and resolving project directories."""

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def project_root(self, slug: str) -> Path:
        """Return the filesystem root for ``slug``."""

        return self.base_dir / slug

    def initialize(self, slug: str) -> ProjectPaths:
        """Create the directory structure for a project if required."""

        paths = ProjectPaths(self.project_root(slug).resolve())
        paths.ensure()
        return paths

    def resolve(self, slug: str) -> ProjectPaths:
        """Resolve an existing project, raising ``FileNotFoundError`` if missing."""

        paths = ProjectPaths(self.project_root(slug).resolve())
        if not paths.root.exists():
            raise FileNotFoundError(f"Project '{slug}' has not been initialized")
        paths.ensure()
        return paths


__all__ = ["ProjectManager"]
