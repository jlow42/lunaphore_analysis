"""Database models for the Sparc backend."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Project(Base):
    """A logical project grouping datasets and executions."""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    title: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text())
    root_path: Mapped[str] = mapped_column(String(512), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    snapshots: Mapped[list[RunSnapshot]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    ingests: Mapped[list[IngestRecord]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    preprocess_jobs: Mapped[list["PreprocessJob"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class RunSnapshot(Base):
    """Immutable capture of a run's configuration state."""

    __tablename__ = "run_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE")
    )
    run_name: Mapped[str] = mapped_column(String(255), index=True)
    manifest_path: Mapped[str] = mapped_column(String(512), nullable=False)
    git_hash: Mapped[str | None] = mapped_column(String(64))
    dependencies: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    inputs: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    project: Mapped[Project] = relationship(back_populates="snapshots")
    ingests: Mapped[list[IngestRecord]] = relationship(back_populates="snapshot")


class IngestRecord(Base):
    """Record describing an imagery ingestion request."""

    __tablename__ = "ingest_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE")
    )
    snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("run_snapshots.id", ondelete="SET NULL"), nullable=True
    )
    source_path: Mapped[str] = mapped_column(String(512))
    panel_csv_path: Mapped[str | None] = mapped_column(String(512))
    zarr_path: Mapped[str | None] = mapped_column(String(512))
    convert_to_zarr: Mapped[bool] = mapped_column(default=False)
    channel_metadata: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    scale_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    panel_mapping: Mapped[dict[str, str] | None] = mapped_column(JSON)
    request_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), default="queued")
    error_message: Mapped[str | None] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    project: Mapped[Project] = relationship(back_populates="ingests")
    snapshot: Mapped[RunSnapshot | None] = relationship(back_populates="ingests")
    preprocess_jobs: Mapped[list["PreprocessJob"]] = relationship(
        back_populates="ingest_record", cascade="all, delete-orphan"
    )


class PreprocessJob(Base):
    """Background preprocessing job tracking."""

    __tablename__ = "preprocess_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE")
    )
    ingest_record_id: Mapped[int] = mapped_column(
        ForeignKey("ingest_records.id", ondelete="CASCADE")
    )
    method: Mapped[str] = mapped_column(String(64))
    output_name: Mapped[str] = mapped_column(String(128))
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="queued")
    progress: Mapped[float] = mapped_column(default=0.0)
    result_zarr_path: Mapped[str | None] = mapped_column(String(512))
    qc_metrics: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    project: Mapped[Project] = relationship(back_populates="preprocess_jobs")
    ingest_record: Mapped[IngestRecord] = relationship(
        back_populates="preprocess_jobs"
    )


__all__ = ["Project", "RunSnapshot", "IngestRecord", "PreprocessJob"]
