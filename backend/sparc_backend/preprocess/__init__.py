"""Preprocessing utilities for background and illumination correction."""

from .background import (
    BackgroundComputationResult,
    BackgroundMethod,
    BackgroundParameters,
    compute_background,
)
from .configs import load_background_configs

__all__ = [
    "BackgroundComputationResult",
    "BackgroundMethod",
    "BackgroundParameters",
    "compute_background",
    "load_background_configs",
]
