"""FastAPI application for the Sparc backend."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .database import Base, get_engine, get_session
from .models import IngestRecord, Project, RunSnapshot
from .projects import ProjectManager, SnapshotManager
from .schemas import (
    IngestRequest,
    IngestResponse,
    IngestStatusModel,
    ProjectCreateRequest,
    ProjectLayout,
    ProjectResponse,
    RunSnapshotModel,
)
from .tasks import enqueue_ingest

settings = get_settings()
engine = get_engine()
project_manager = ProjectManager(settings.projects_root)
snapshot_manager = SnapshotManager(settings.repo_root)

SessionDep = Annotated[Session, Depends(get_session)]

app = FastAPI(title="Sparc API")


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)


@app.get("/healthz")
async def healthcheck() -> dict[str, str]:
    """Health check endpoint."""

    return {"status": "ok"}


def _layout_for(project: Project) -> ProjectLayout:
    paths = project_manager.initialize(project.slug)
    layout = paths.as_dict()
    layout["root"] = str(paths.root)
    return ProjectLayout(**layout)


@app.post("/projects", response_model=ProjectResponse, status_code=201)
def create_project(
    payload: ProjectCreateRequest,
    session: SessionDep,
) -> ProjectResponse:
    existing = session.scalar(select(Project).where(Project.slug == payload.slug))
    try:
        paths = project_manager.initialize(payload.slug)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if existing is None:
        project = Project(
            slug=payload.slug,
            title=payload.title,
            description=payload.description,
            root_path=str(paths.root),
        )
        session.add(project)
    else:
        existing.title = payload.title
        existing.description = payload.description
        existing.root_path = str(paths.root)
        project = existing
    session.commit()
    session.refresh(project)
    return ProjectResponse(
        slug=project.slug,
        title=project.title,
        description=project.description,
        root_path=project.root_path,
        created_at=project.created_at,
        layout=_layout_for(project),
    )


@app.get("/projects", response_model=list[ProjectResponse])
def list_projects(session: SessionDep) -> list[ProjectResponse]:
    projects = session.scalars(select(Project).order_by(Project.created_at)).all()
    return [
        ProjectResponse(
            slug=project.slug,
            title=project.title,
            description=project.description,
            root_path=project.root_path,
            created_at=project.created_at,
            layout=_layout_for(project),
        )
        for project in projects
    ]


@app.get("/projects/{slug}", response_model=ProjectResponse)
def get_project(slug: str, session: SessionDep) -> ProjectResponse:
    project = session.scalar(select(Project).where(Project.slug == slug))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectResponse(
        slug=project.slug,
        title=project.title,
        description=project.description,
        root_path=project.root_path,
        created_at=project.created_at,
        layout=_layout_for(project),
    )


@app.post("/ingest", response_model=IngestResponse, status_code=202)
def submit_ingest(
    payload: IngestRequest,
    session: SessionDep,
) -> IngestResponse:
    project = session.scalar(
        select(Project).where(Project.slug == payload.project_slug)
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        project_paths = project_manager.initialize(project.slug)
        image_path = project_manager.resolve_project_path(
            project.slug, payload.image_path
        )
        panel_csv_path = (
            project_manager.resolve_project_path(project.slug, payload.panel_csv_path)
            if payload.panel_csv_path
            else None
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    input_paths = [image_path]
    if panel_csv_path:
        input_paths.append(panel_csv_path)
    snapshot_record = snapshot_manager.capture(
        project_paths, payload.run_name, input_paths
    )

    snapshot = RunSnapshot(
        project_id=project.id,
        run_name=payload.run_name,
        manifest_path=str(snapshot_record.manifest_path),
        git_hash=snapshot_record.git_hash,
        dependencies=snapshot_record.dependencies,
        inputs=snapshot_record.inputs,
        created_at=snapshot_record.created_at,
    )
    session.add(snapshot)
    session.flush()

    ingest_record = IngestRecord(
        project_id=project.id,
        snapshot_id=snapshot.id,
        source_path=str(image_path),
        panel_csv_path=str(panel_csv_path) if panel_csv_path else None,
        convert_to_zarr=payload.convert_to_zarr,
        request_metadata=dict(payload.metadata),
        status="queued",
    )
    session.add(ingest_record)
    session.commit()

    task = enqueue_ingest(ingest_record.id)
    snapshot_model = RunSnapshotModel.model_validate(snapshot)
    project_response = ProjectResponse(
        slug=project.slug,
        title=project.title,
        description=project.description,
        root_path=project.root_path,
        created_at=project.created_at,
        layout=_layout_for(project),
    )
    return IngestResponse(
        task_id=str(task.id),
        ingest_record_id=ingest_record.id,
        project=project_response,
        snapshot=snapshot_model,
    )


@app.get("/ingest/{ingest_id}", response_model=IngestStatusModel)
def get_ingest_status(
    ingest_id: int,
    session: SessionDep,
) -> IngestStatusModel:
    record = session.get(IngestRecord, ingest_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Ingest record not found")
    return IngestStatusModel.model_validate(record)
