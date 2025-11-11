"""Project management utilities."""

from __future__ import annotations

import re
from pathlib import Path

from .paths import ProjectPaths


class ProjectManager:
    """Responsible for creating and resolving project directories."""

    _SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir.resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _validate_slug(self, slug: str) -> None:
        if not self._SLUG_PATTERN.fullmatch(slug):
            raise ValueError(
                "Project slug may only contain lowercase letters, numbers, hyphens, or underscores",
            )

    def _ensure_within_base(self, path: Path) -> Path:
        try:
            path.relative_to(self.base_dir)
        except ValueError as exc:
            raise ValueError(
                "Project path resolves outside the configured projects directory",
            ) from exc
        return path

    def project_root(self, slug: str) -> Path:
        """Return the filesystem root for ``slug``."""

        self._validate_slug(slug)
        candidate = (self.base_dir / slug).resolve()
        return self._ensure_within_base(candidate)

    def initialize(self, slug: str) -> ProjectPaths:
        """Create the directory structure for a project if required."""

        paths = ProjectPaths(self.project_root(slug))
        paths.ensure()
        return paths

    def resolve(self, slug: str) -> ProjectPaths:
        """Resolve an existing project, raising ``FileNotFoundError`` if missing."""

        paths = ProjectPaths(self.project_root(slug))
        if not paths.root.exists():
            raise FileNotFoundError(f"Project '{slug}' has not been initialized")
        paths.ensure()
        return paths

    def resolve_project_path(self, slug: str, path: Path) -> Path:
        """Resolve ``path`` relative to the project root, ensuring it stays within it."""

        project_root = self.project_root(slug)
        candidate = path.expanduser()
        if not candidate.is_absolute():
            candidate = project_root / candidate
        resolved = candidate.resolve()
        try:
            resolved.relative_to(project_root)
        except ValueError as exc:
            raise ValueError(
                "Provided path is outside the project root",
            ) from exc
        return resolved


__all__ = ["ProjectManager"]
