"""Celery tasks for background processing."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import dask.array as da
import numpy as np
import zarr
from aicsimageio import AICSImage
from anndata import AnnData
import anndata as ad
from celery import Celery

from .config import get_settings
from .database import session_scope
from .ingest import (
    IngestError,
    convert_to_ome_zarr,
    extract_metadata,
    load_panel_mapping,
)
from .models import IngestRecord, PreprocessJob
from .preprocess import compute_background
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


def enqueue_background_job(preprocess_job_id: int):
    """Enqueue a background preprocessing job."""

    return preprocess_background.delay(preprocess_job_id=preprocess_job_id)


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


def _load_imagery(record: IngestRecord) -> da.Array:
    """Load imagery for preprocessing as a Dask array."""

    if record.zarr_path:
        store_path = Path(record.zarr_path)
        return da.from_zarr(str(store_path), component="0")

    source_path = Path(record.source_path)
    if not source_path.exists():
        source_path = PROJECT_MANAGER.resolve_project_path(
            record.project.slug, Path(record.source_path)
        )
    image = AICSImage(str(source_path))
    data = image.get_image_data("CZYX", T=0)
    return da.from_array(data, chunks=(1, 1, 256, 256))


def _write_background_results(
    output_path: Path,
    corrected: da.Array,
    background: da.Array,
    scale_metadata: dict[str, Any] | None,
    method: str,
    parameters: dict[str, Any],
    channels: list[int] | None,
) -> None:
    """Persist corrected imagery and metadata to a Zarr store."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    store = zarr.DirectoryStore(str(output_path))
    root = zarr.group(store=store, overwrite=True)

    da.to_zarr(corrected, store, component="corrected", overwrite=True)
    da.to_zarr(background, store, component="background", overwrite=True)

    scale_z = float(scale_metadata.get("z", 1.0)) if scale_metadata else 1.0
    scale_y = float(scale_metadata.get("y", 1.0)) if scale_metadata else 1.0
    scale_x = float(scale_metadata.get("x", 1.0)) if scale_metadata else 1.0

    root.attrs.update(
        {
            "multiscales": [
                {
                    "version": "0.4",
                    "name": f"{method}_correction",
                    "axes": [
                        {"name": "c", "type": "channel"},
                        {"name": "z", "type": "space"},
                        {"name": "y", "type": "space"},
                        {"name": "x", "type": "space"},
                    ],
                    "datasets": [
                        {
                            "path": "corrected",
                            "coordinateTransformations": [
                                {
                                    "type": "scale",
                                    "scale": [1.0, scale_z, scale_y, scale_x],
                                }
                            ],
                        }
                    ],
                }
            ],
            "sparc_background": {
                "method": method,
                "parameters": parameters,
                "channels": channels,
            },
        }
    )


def _update_anndata(
    job: PreprocessJob,
    output_path: Path,
    qc_metrics: dict[str, Any],
    parameters: dict[str, Any],
    channels: list[int] | None,
) -> None:
    project_paths = PROJECT_MANAGER.resolve(job.project.slug)
    adata_path = project_paths.h5ad / f"ingest_{job.ingest_record_id}.h5ad"
    adata_path.parent.mkdir(parents=True, exist_ok=True)
    if adata_path.exists():
        adata = ad.read_h5ad(str(adata_path))
    else:
        adata = AnnData(np.zeros((0, 0)))

    background_uns = adata.uns.setdefault("background_corrections", {})
    background_uns[job.output_name] = {
        "method": job.method,
        "parameters": parameters,
        "channels": channels,
        "qc_metrics": qc_metrics,
        "result_zarr_path": str(output_path),
        "components": {
            "corrected": "corrected",
            "background": "background",
        },
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    adata.write_h5ad(str(adata_path))


@celery_app.task(name="sparc_backend.preprocess_background")
def preprocess_background(*, preprocess_job_id: int) -> dict[str, Any]:
    """Execute a background correction job."""

    with session_scope() as session:
        job = session.get(PreprocessJob, preprocess_job_id)
        if job is None:
            LOGGER.error("Preprocess job %s not found", preprocess_job_id)
            return {"status": "missing"}

        job.status = "running"
        job.progress = 0.05
        job.updated_at = datetime.now(timezone.utc)
        session.add(job)
        session.flush()

        try:
            data = _load_imagery(job.ingest_record)
            params = dict(job.parameters or {})
            channel_selection = params.pop("channels", None)
            result = compute_background(
                data,
                method=job.method,
                params=params,
                channels=channel_selection,
            )
            project_paths = PROJECT_MANAGER.resolve(job.project.slug)
            output_dir = project_paths.imagery / "preprocessing"
            output_path = output_dir / f"{job.output_name}_{job.method}.zarr"
            _write_background_results(
                output_path,
                result.corrected,
                result.background,
                job.ingest_record.scale_metadata or {},
                job.method,
                params,
                channel_selection,
            )
            job.result_zarr_path = str(output_path)
            job.qc_metrics = result.qc_metrics
            job.progress = 0.95
            _update_anndata(job, output_path, result.qc_metrics, params, channel_selection)
            job.status = "completed"
            job.error_message = None
            job.progress = 1.0
        except Exception as exc:  # pragma: no cover - defensive catch-all
            LOGGER.exception("Background preprocessing failed for job %s", preprocess_job_id)
            job.status = "failed"
            job.error_message = str(exc)
        finally:
            job.updated_at = datetime.now(timezone.utc)
            session.add(job)
            session.flush()

        return {
            "status": job.status,
            "job_id": job.id,
            "result_zarr_path": job.result_zarr_path,
            "qc_metrics": job.qc_metrics,
        }


__all__ = [
    "celery_app",
    "enqueue_ingest",
    "enqueue_background_job",
    "ingest_image",
    "preprocess_background",
]
