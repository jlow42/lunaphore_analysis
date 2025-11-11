"""Pydantic schemas for the Sparc backend API."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProjectLayout(BaseModel):
    """Filesystem layout for a project."""

    root: str
    imagery: str
    masks: str
    h5ad: str
    spatialdata: str
    configs: str
    logs: str
    snapshots: str


class ProjectCreateRequest(BaseModel):
    """Request body for creating a project."""

    slug: str = Field(..., min_length=1)
    title: str | None = None
    description: str | None = None


class ProjectResponse(BaseModel):
    """Project response payload."""

    model_config = ConfigDict(from_attributes=True)

    slug: str
    title: str | None = None
    description: str | None = None
    root_path: str
    created_at: datetime
    layout: ProjectLayout


class RunSnapshotModel(BaseModel):
    """Representation of a run snapshot."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    run_name: str
    manifest_path: str
    git_hash: str | None
    dependencies: list[dict[str, str]]
    inputs: list[dict[str, str]]
    created_at: datetime


class IngestRequest(BaseModel):
    """Request body for imagery ingestion."""

    project_slug: str
    run_name: str
    image_path: Path
    convert_to_zarr: bool = False
    panel_csv_path: Path | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class IngestResponse(BaseModel):
    """Response describing an ingestion task submission."""

    task_id: str
    ingest_record_id: int
    project: ProjectResponse
    snapshot: RunSnapshotModel


class IngestStatusModel(BaseModel):
    """Status payload for ingestion records."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    source_path: str
    panel_csv_path: str | None
    zarr_path: str | None
    channel_metadata: list[dict[str, Any]] | None
    scale_metadata: dict[str, Any] | None
    panel_mapping: dict[str, str] | None
    request_metadata: dict[str, Any] | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class BackgroundMethodParameter(BaseModel):
    """Parameter definition for background correction."""

    name: str
    label: str
    type: str
    default: Any | None = None
    minimum: float | None = None
    maximum: float | None = None
    choices: list[Any] | None = None
    description: str | None = None


class BackgroundMethodConfig(BaseModel):
    """Configuration for a background correction method."""

    name: str
    label: str
    description: str | None = None
    parameters: list[BackgroundMethodParameter] = Field(default_factory=list)


class BackgroundConfigResponse(BaseModel):
    """Available background preprocessing methods."""

    methods: list[BackgroundMethodConfig]


class BackgroundPreprocessRequest(BaseModel):
    """Submission payload for background correction jobs."""

    project_slug: str
    ingest_record_id: int
    method: str
    output_name: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    channels: list[int] | None = None


class BackgroundPreprocessResponse(BaseModel):
    """Response describing an enqueued background job."""

    task_id: str
    job_id: int
    status: str


class BackgroundPreprocessStatus(BaseModel):
    """Status payload for background preprocessing jobs."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    method: str
    output_name: str
    status: str
    progress: float
    result_zarr_path: str | None
    qc_metrics: dict[str, Any] | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


__all__ = [
    "ProjectLayout",
    "ProjectCreateRequest",
    "ProjectResponse",
    "RunSnapshotModel",
    "IngestRequest",
    "IngestResponse",
    "IngestStatusModel",
    "BackgroundMethodParameter",
    "BackgroundMethodConfig",
    "BackgroundConfigResponse",
    "BackgroundPreprocessRequest",
    "BackgroundPreprocessResponse",
    "BackgroundPreprocessStatus",
]
