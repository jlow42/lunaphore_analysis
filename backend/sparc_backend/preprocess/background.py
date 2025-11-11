"""Background and illumination correction routines."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable

import dask.array as da
import numpy as np
from dask import delayed
from skimage import filters, morphology, restoration

BackgroundParameters = dict[str, Any]


@dataclass(slots=True)
class BackgroundComputationResult:
    """Result bundle for a preprocessing execution."""

    background: da.Array
    corrected: da.Array
    qc_metrics: dict[str, Any]


@dataclass(slots=True)
class BackgroundMethod:
    """Callable background correction routine."""

    name: str
    handler: Callable[[np.ndarray, BackgroundParameters], tuple[np.ndarray, np.ndarray]]


def _clip_positive(image: np.ndarray) -> np.ndarray:
    corrected = image.copy()
    corrected[corrected < 0] = 0
    return corrected


def _basic_handler(image: np.ndarray, params: BackgroundParameters) -> tuple[np.ndarray, np.ndarray]:
    radius = int(params.get("rolling_ball_radius", 50))
    radius = max(1, radius)
    background = restoration.rolling_ball(image, radius=radius)
    corrected = _clip_positive(image - background)
    return background, corrected


def _polynomial_features(order: int, shape: tuple[int, int]) -> np.ndarray:
    y, x = np.indices(shape)
    features = []
    for i in range(order + 1):
        for j in range(order + 1 - i):
            features.append((x**i) * (y**j))
    return np.stack(features, axis=-1)


def _polynomial_handler(image: np.ndarray, params: BackgroundParameters) -> tuple[np.ndarray, np.ndarray]:
    order = int(params.get("order", 2))
    order = max(1, min(order, 5))
    features = _polynomial_features(order, image.shape)
    design = features.reshape(-1, features.shape[-1])
    target = image.reshape(-1)
    coeffs, *_ = np.linalg.lstsq(design, target, rcond=None)
    background = (design @ coeffs).reshape(image.shape)
    corrected = _clip_positive(image - background)
    return background, corrected


def _morphological_handler(image: np.ndarray, params: BackgroundParameters) -> tuple[np.ndarray, np.ndarray]:
    radius = int(params.get("opening_radius", 15))
    radius = max(1, radius)
    footprint = morphology.disk(radius)
    background = morphology.opening(image, footprint)
    corrected = _clip_positive(image - background)
    return background, corrected


def _adaptive_handler(image: np.ndarray, params: BackgroundParameters) -> tuple[np.ndarray, np.ndarray]:
    block_size = int(params.get("block_size", 35))
    if block_size % 2 == 0:
        block_size += 1
    offset = float(params.get("offset", 0.0))
    background = filters.threshold_local(image, block_size=block_size, offset=offset)
    corrected = _clip_positive(image - background)
    return background, corrected


REGISTERED_METHODS: dict[str, BackgroundMethod] = {
    "basic": BackgroundMethod(name="basic", handler=_basic_handler),
    "polynomial": BackgroundMethod(name="polynomial", handler=_polynomial_handler),
    "morphological": BackgroundMethod(name="morphological", handler=_morphological_handler),
    "adaptive": BackgroundMethod(name="adaptive", handler=_adaptive_handler),
}


def _apply_method(
    plane: da.Array,
    handler: Callable[[np.ndarray, BackgroundParameters], tuple[np.ndarray, np.ndarray]],
    params: BackgroundParameters,
    dtype: np.dtype,
) -> tuple[da.Array, da.Array]:
    """Apply a correction handler to a single 2D plane and wrap it in Dask arrays."""

    plane_delayed = plane.to_delayed().ravel()[0]

    @delayed
    def _compute(payload: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        background, corrected = handler(np.asarray(payload), params)
        return background.astype(dtype, copy=False), corrected.astype(dtype, copy=False)

    background_delayed, corrected_delayed = _compute(plane_delayed)
    shape = tuple(int(dim) for dim in plane.shape)
    background_da = da.from_delayed(background_delayed, shape=shape, dtype=dtype)
    corrected_da = da.from_delayed(corrected_delayed, shape=shape, dtype=dtype)
    return background_da, corrected_da


def _per_channel(
    data: da.Array,
    handler: Callable[[np.ndarray, BackgroundParameters], tuple[np.ndarray, np.ndarray]],
    params: BackgroundParameters,
) -> tuple[da.Array, da.Array]:
    dtype = np.float32 if np.issubdtype(data.dtype, np.integer) else data.dtype
    rechunked = data.rechunk((1, 1, -1, -1))
    background_planes: list[list[da.Array]] = []
    corrected_planes: list[list[da.Array]] = []
    for c in range(rechunked.shape[0]):
        bg_slices: list[da.Array] = []
        corrected_slices: list[da.Array] = []
        for z in range(rechunked.shape[1]):
            background_plane, corrected_plane = _apply_method(
                rechunked[c, z, :, :], handler, params, np.dtype(dtype)
            )
            bg_slices.append(background_plane)
            corrected_slices.append(corrected_plane)
        background_planes.append(da.stack(bg_slices, axis=0))
        corrected_planes.append(da.stack(corrected_slices, axis=0))
    background = da.stack(background_planes, axis=0)
    corrected = da.stack(corrected_planes, axis=0)
    return background.astype(dtype), corrected.astype(dtype)


def _stats(arr: da.Array) -> dict[str, float]:
    return {
        "mean": float(arr.mean().compute()),
        "std": float(arr.std().compute()),
        "min": float(arr.min().compute()),
        "max": float(arr.max().compute()),
    }


def _channel_stats(arr: da.Array) -> list[dict[str, float]]:
    summaries: list[dict[str, float]] = []
    for idx in range(arr.shape[0]):
        channel = arr[idx]
        summaries.append({"channel_index": idx, **_stats(channel)})
    return summaries


def compute_background(
    data: da.Array,
    *,
    method: str,
    params: BackgroundParameters,
    channels: Iterable[int] | None = None,
) -> BackgroundComputationResult:
    """Execute a background correction routine on the provided data."""

    if method not in REGISTERED_METHODS:
        raise ValueError(f"Unsupported background method '{method}'")
    handler = REGISTERED_METHODS[method].handler

    if channels is not None:
        channel_indices = list(channels)
        if not channel_indices:
            raise ValueError("Channel selection cannot be empty")
        subset = data[channel_indices]
    else:
        subset = data

    background, corrected = _per_channel(subset, handler, params)

    qc_metrics = {
        "raw": _stats(subset),
        "background": _stats(background),
        "corrected": _stats(corrected),
        "per_channel": _channel_stats(corrected),
    }

    return BackgroundComputationResult(background=background, corrected=corrected, qc_metrics=qc_metrics)


__all__ = [
    "BackgroundParameters",
    "BackgroundComputationResult",
    "BackgroundMethod",
    "REGISTERED_METHODS",
    "compute_background",
]
