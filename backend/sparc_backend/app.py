"""FastAPI application for the Sparc backend."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .database import Base, get_engine, get_session
from .models import IngestRecord, PreprocessJob, Project, RunSnapshot
from .projects import ProjectManager, SnapshotManager
from .schemas import (
    BackgroundConfigResponse,
    BackgroundMethodConfig,
    BackgroundMethodParameter,
    BackgroundPreprocessRequest,
    BackgroundPreprocessResponse,
    BackgroundPreprocessStatus,
    IngestRequest,
    IngestResponse,
    IngestStatusModel,
    ProjectCreateRequest,
    ProjectLayout,
    ProjectResponse,
    RunSnapshotModel,
)
from .preprocess import load_background_configs
from .tasks import enqueue_background_job, enqueue_ingest

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


@app.get("/preprocess/background/config", response_model=BackgroundConfigResponse)
def get_background_config() -> BackgroundConfigResponse:
    """Return available background preprocessing methods."""

    return _background_config_response()


def _layout_for(project: Project) -> ProjectLayout:
    paths = project_manager.initialize(project.slug)
    layout = paths.as_dict()
    layout["root"] = str(paths.root)
    return ProjectLayout(**layout)


def _background_config_response() -> BackgroundConfigResponse:
    methods = []
    for method in load_background_configs():
        parameters = [
            BackgroundMethodParameter(
                name=param.name,
                label=param.label,
                type=param.type,
                default=param.default,
                minimum=param.minimum,
                maximum=param.maximum,
                choices=param.choices,
                description=param.description,
            )
            for param in method.parameters
        ]
        methods.append(
            BackgroundMethodConfig(
                name=method.name,
                label=method.label,
                description=method.description,
                parameters=parameters,
            )
        )
    return BackgroundConfigResponse(methods=methods)


def _validate_background_parameters(
    method_name: str, parameters: dict[str, object]
) -> dict[str, object]:
    methods = {method.name: method for method in load_background_configs()}
    if method_name not in methods:
        raise HTTPException(status_code=400, detail=f"Unknown method '{method_name}'")

    method = methods[method_name]
    allowed = {param.name: param for param in method.parameters}
    sanitized: dict[str, object] = {}

    for key, value in parameters.items():
        if key not in allowed:
            raise HTTPException(status_code=400, detail=f"Unsupported parameter '{key}'")
        param = allowed[key]
        numeric_types = (int, float)
        if isinstance(value, numeric_types):
            if param.minimum is not None and float(value) < float(param.minimum):
                raise HTTPException(
                    status_code=400,
                    detail=f"Parameter '{key}' below minimum {param.minimum}",
                )
            if param.maximum is not None and float(value) > float(param.maximum):
                raise HTTPException(
                    status_code=400,
                    detail=f"Parameter '{key}' above maximum {param.maximum}",
                )
        if param.choices and value not in param.choices:
            raise HTTPException(
                status_code=400,
                detail=f"Parameter '{key}' must be one of {param.choices}",
            )
        sanitized[key] = value

    for name, param in allowed.items():
        if name not in sanitized and param.default is not None:
            sanitized[name] = param.default

    return sanitized


def _sanitize_output_name(name: str) -> str:
    sanitized = name.strip().replace(" ", "_")
    if not sanitized:
        raise HTTPException(status_code=400, detail="Output name cannot be empty")
    return sanitized


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


@app.post(
    "/preprocess/background",
    response_model=BackgroundPreprocessResponse,
    status_code=202,
)
def submit_background_preprocess(
    payload: BackgroundPreprocessRequest,
    session: SessionDep,
) -> BackgroundPreprocessResponse:
    project = session.scalar(select(Project).where(Project.slug == payload.project_slug))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    ingest_record = session.get(IngestRecord, payload.ingest_record_id)
    if ingest_record is None or ingest_record.project_id != project.id:
        raise HTTPException(status_code=404, detail="Ingest record not found for project")

    parameters = _validate_background_parameters(payload.method, payload.parameters)
    if payload.channels is not None:
        if any(channel < 0 for channel in payload.channels):
            raise HTTPException(status_code=400, detail="Channel indices must be non-negative")
        parameters["channels"] = payload.channels

    job = PreprocessJob(
        project_id=project.id,
        ingest_record_id=ingest_record.id,
        method=payload.method,
        output_name=_sanitize_output_name(payload.output_name),
        parameters=parameters,
        status="queued",
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    task = enqueue_background_job(job.id)

    return BackgroundPreprocessResponse(
        task_id=str(task.id),
        job_id=job.id,
        status=job.status,
    )


@app.get(
    "/preprocess/background/{job_id}",
    response_model=BackgroundPreprocessStatus,
)
def get_background_status(job_id: int, session: SessionDep) -> BackgroundPreprocessStatus:
    job = session.get(PreprocessJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Preprocess job not found")
    return BackgroundPreprocessStatus.model_validate(job)


@app.get("/ingest/{ingest_id}", response_model=IngestStatusModel)
def get_ingest_status(
    ingest_id: int,
    session: SessionDep,
) -> IngestStatusModel:
    record = session.get(IngestRecord, ingest_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Ingest record not found")
    return IngestStatusModel.model_validate(record)
