"""Utilities for immutable run snapshot capture."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

from git import InvalidGitRepositoryError, NoSuchPathError, Repo

from .paths import ProjectPaths


@dataclass(slots=True)
class SnapshotRecord:
    """Details about a persisted run snapshot."""

    run_name: str
    manifest_path: Path
    git_hash: str | None
    dependencies: list[dict[str, str]]
    inputs: list[dict[str, str]]
    created_at: datetime

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable representation of the snapshot."""

        return {
            "run_name": self.run_name,
            "manifest_path": str(self.manifest_path),
            "git_hash": self.git_hash,
            "dependencies": self.dependencies,
            "inputs": self.inputs,
            "created_at": self.created_at.isoformat(),
        }


class SnapshotManager:
    """Capture run manifests for reproducibility."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root

    def capture(
        self, project_paths: ProjectPaths, run_name: str, input_paths: Sequence[Path]
    ) -> SnapshotRecord:
        """Capture a run snapshot and persist it under ``project_paths``."""

        project_paths.snapshots.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc)
        slug = self._slugify(run_name)
        manifest_path = (
            project_paths.snapshots
            / f"{timestamp.strftime('%Y%m%dT%H%M%SZ')}_{slug}.json"
        )

        dependencies = self._dependency_manifests()
        inputs = self._input_manifests(input_paths, project_paths.root)
        git_hash = self._git_revision()

        manifest = {
            "run_name": run_name,
            "created_at": timestamp.isoformat(),
            "git": {"hash": git_hash},
            "dependencies": dependencies,
            "inputs": inputs,
        }
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
        )

        return SnapshotRecord(
            run_name=run_name,
            manifest_path=manifest_path,
            git_hash=git_hash,
            dependencies=dependencies,
            inputs=inputs,
            created_at=timestamp,
        )

    def _git_revision(self) -> str | None:
        try:
            repo = Repo(self.repo_root, search_parent_directories=True)
        except (InvalidGitRepositoryError, NoSuchPathError):
            return None
        return repo.head.commit.hexsha

    def _dependency_manifests(self) -> list[dict[str, str]]:
        manifests: list[dict[str, str]] = []
        candidates = [
            Path("pyproject.toml"),
            Path("poetry.lock"),
            Path("uv.lock"),
            Path("pnpm-workspace.yaml"),
            Path("frontend/pnpm-lock.yaml"),
            Path("frontend/package.json"),
        ]
        for candidate in candidates:
            path = (self.repo_root / candidate).resolve()
            if not path.exists():
                continue
            manifests.append(
                {
                    "path": str(candidate),
                    "sha256": self._hash_file(path),
                }
            )
        return manifests

    def _input_manifests(
        self, paths: Iterable[Path], project_root: Path
    ) -> list[dict[str, str]]:
        manifests: list[dict[str, str]] = []
        seen: set[Path] = set()
        for path in paths:
            resolved = path.expanduser().resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            entry: dict[str, str] = {
                "path": str(self._relative_to_project(resolved, project_root)),
                "sha256": self._hash_file(resolved) if resolved.exists() else "",
            }
            manifests.append(entry)
        return manifests

    @staticmethod
    def _relative_to_project(path: Path, project_root: Path) -> Path:
        try:
            return path.relative_to(project_root)
        except ValueError:
            return path

    @staticmethod
    def _hash_file(path: Path) -> str:
        if not path.exists() or not path.is_file():
            return ""
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _slugify(value: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip())
        slug = slug.strip("-").lower()
        return slug or "run"


__all__ = ["SnapshotManager", "SnapshotRecord"]
