"""Celery worker entry point."""

from __future__ import annotations

from .tasks import celery_app


def main() -> None:
    """Launch the Celery worker with sane defaults."""

    celery_app.worker_main(["worker", "--loglevel=INFO"])


if __name__ == "__main__":  # pragma: no cover
    main()
