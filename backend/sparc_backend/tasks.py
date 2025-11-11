"""Celery tasks for background processing."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from celery import Celery

from .config import get_settings
from .database import session_scope
from .ingest import (
    IngestError,
    convert_to_ome_zarr,
    extract_metadata,
    load_panel_mapping,
)
from .models import IngestRecord
from .projects import ProjectManager

LOGGER = logging.getLogger(__name__)
SETTINGS = get_settings()
PROJECT_MANAGER = ProjectManager(SETTINGS.projects_root)

celery_app = Celery(
    "sparc_backend", broker=SETTINGS.redis_url, backend=SETTINGS.redis_url
)
celery_app.conf.task_serializer = "json"
celery_app.conf.result_serializer = "json"
celery_app.conf.accept_content = ["json"]


def enqueue_ingest(ingest_record_id: int):
    """Enqueue an ingestion job and return the Celery result handle."""

    return ingest_image.delay(ingest_record_id=ingest_record_id)


@celery_app.task(name="sparc_backend.ingest_image")
def ingest_image(*, ingest_record_id: int) -> dict[str, Any]:
    """Process an ingestion request."""

    with session_scope() as session:
        record = session.get(IngestRecord, ingest_record_id)
        if record is None:
            LOGGER.error("Ingest record %s not found", ingest_record_id)
            return {"status": "missing"}

        project = record.project
        project_paths = PROJECT_MANAGER.resolve(project.slug)
        metadata: dict[str, Any]
        panel_mapping: dict[str, str] = {}
        try:
            try:
                source_path = PROJECT_MANAGER.resolve_project_path(
                    project.slug, Path(record.source_path)
                )
                panel_csv_path: Path | None = None
                if record.panel_csv_path:
                    panel_csv_path = PROJECT_MANAGER.resolve_project_path(
                        project.slug, Path(record.panel_csv_path)
                    )
                    panel_mapping = load_panel_mapping(panel_csv_path)
            except ValueError as exc:
                raise IngestError(str(exc)) from exc
            metadata = extract_metadata(source_path, panel_mapping)
            zarr_path: Path | None = None
            if record.convert_to_zarr:
                zarr_dir = project_paths.imagery / f"{source_path.stem}.zarr"
                zarr_path = convert_to_ome_zarr(
                    source_path,
                    zarr_dir,
                    metadata["channels"],
                    metadata["scale"],
                )
                record.zarr_path = str(zarr_path)
            record.channel_metadata = metadata["channels"]
            record.scale_metadata = metadata["scale"]
            record.panel_mapping = panel_mapping or None
            record.status = "completed"
            record.error_message = None
        except IngestError as exc:
            LOGGER.exception("Ingestion failed for record %s", ingest_record_id)
            record.status = "failed"
            record.error_message = str(exc)
        except Exception:  # pragma: no cover - defensive catch-all
            LOGGER.exception("Unexpected failure during ingestion")
            record.status = "failed"
            record.error_message = "Unexpected ingestion failure"
        finally:
            record.updated_at = datetime.now(timezone.utc)
        session.add(record)
        session.flush()

        return {
            "status": record.status,
            "record_id": record.id,
            "panel_mapping": record.panel_mapping,
            "channel_count": len(record.channel_metadata or []),
            "zarr_path": record.zarr_path,
        }


__all__ = ["celery_app", "enqueue_ingest", "ingest_image"]
