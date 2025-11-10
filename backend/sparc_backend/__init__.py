"""Backend package for Sparc platform services."""

from importlib import metadata

from .tasks import celery_app

__all__ = ["__version__", "celery_app"]


def __getattr__(name: str) -> str:
    if name == "__version__":
        try:
            return metadata.version("sparc-platform")
        except (
            metadata.PackageNotFoundError
        ):  # pragma: no cover - fallback for dev installs
            return "0.0.0"
    if name == "celery_app":
        return celery_app
    raise AttributeError(name)
