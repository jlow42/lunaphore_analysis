# SPARC Backend

Placeholder for FastAPI services, pipeline orchestration, and background workers.

## Planned Structure
- `app/` – FastAPI application package.
- `services/` – domain services (ingest, preprocess, segmentation, analytics).
- `workers/` – Celery/RQ task definitions.
- `models/` – Pydantic schemas and ORM models.
- `tests/` – backend unit/integration tests.

Refer to `../docs/system_overview.md` for the full architecture specification.
