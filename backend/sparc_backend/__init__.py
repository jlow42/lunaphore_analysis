"""Backend package for Sparc platform services."""

from importlib import metadata

__all__ = ["__version__"]


def __getattr__(name: str) -> str:
    if name == "__version__":
        try:
            return metadata.version("sparc-platform")
        except metadata.PackageNotFoundError:  # pragma: no cover - fallback for dev installs
            return "0.0.0"
    raise AttributeError(name)
