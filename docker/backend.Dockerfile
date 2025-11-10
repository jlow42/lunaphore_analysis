FROM ghcr.io/astral-sh/uv:python3.11

WORKDIR /app

COPY pyproject.toml pyproject.toml
COPY backend backend
COPY cli cli

RUN uv sync --no-dev

ENV PYTHONPATH=/app/backend:/app/cli

CMD ["uv", "run", "uvicorn", "sparc_backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
