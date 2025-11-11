"""Ingestion helpers for imagery and metadata."""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any, Iterable

import zarr
from aicsimageio import AICSImage
from aicsimageio.exceptions import UnsupportedFileFormatError
from numcodecs import Blosc
from tifffile import TiffFileError

LOGGER = logging.getLogger(__name__)


class IngestError(RuntimeError):
    """Raised when imagery ingestion fails."""


def load_panel_mapping(panel_path: Path) -> dict[str, str]:
    """Load channel remapping information from a panel CSV file."""

    mapping: dict[str, str] = {}
    try:
        with panel_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                channel = (
                    row.get("channel") or row.get("Channel") or row.get("Channel Name")
                )
                target = row.get("target") or row.get("Target") or row.get("Marker")
                if channel and target:
                    mapping[channel.strip()] = target.strip()
    except FileNotFoundError as exc:
        raise IngestError(f"Panel CSV not found: {panel_path}") from exc
    except csv.Error as exc:  # pragma: no cover - malformed CSVs are uncommon
        raise IngestError(f"Failed to parse panel CSV {panel_path}: {exc}") from exc
    return mapping


def extract_metadata(image_path: Path, panel_mapping: dict[str, str]) -> dict[str, Any]:
    """Extract channel and scale metadata from an OME-TIFF."""

    try:
        image = AICSImage(str(image_path))
    except (FileNotFoundError, UnsupportedFileFormatError, TiffFileError) as exc:
        raise IngestError(f"Unable to open image {image_path}: {exc}") from exc

    channel_names = image.channel_names
    if not channel_names:
        channel_names = [f"C{idx}" for idx in range(image.dims.C)]

    channels: list[dict[str, Any]] = []
    for index, name in enumerate(channel_names):
        remapped = panel_mapping.get(name) or panel_mapping.get(str(index))
        channels.append(
            {
                "index": index,
                "name": name,
                "remapped_name": remapped,
            }
        )

    pixel_sizes = image.physical_pixel_sizes
    scale = {
        "x": getattr(pixel_sizes, "X", None) or 1.0,
        "y": getattr(pixel_sizes, "Y", None) or 1.0,
        "z": getattr(pixel_sizes, "Z", None) or 1.0,
    }

    metadata = {
        "channels": channels,
        "scale": scale,
        "scenes": list(image.scenes),
        "dims": {
            "c": image.dims.C,
            "z": image.dims.Z,
            "y": image.dims.Y,
            "x": image.dims.X,
        },
    }
    return metadata


def convert_to_ome_zarr(
    image_path: Path,
    output_path: Path,
    channels: Iterable[dict[str, Any]],
    scale: dict[str, float],
) -> Path:
    """Persist the imagery as a single-resolution OME-Zarr store."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        image = AICSImage(str(image_path))
    except (FileNotFoundError, UnsupportedFileFormatError, TiffFileError) as exc:
        raise IngestError(f"Unable to open image {image_path}: {exc}") from exc

    data = image.get_image_data("CZYX", T=0)
    store = zarr.DirectoryStore(str(output_path))
    root = zarr.group(store=store, overwrite=True)

    chunks = (
        min(1, data.shape[0]) or 1,
        min(1, data.shape[1]) or 1,
        min(256, data.shape[2]),
        min(256, data.shape[3]),
    )
    compressor = Blosc(cname="zstd", clevel=5, shuffle=Blosc.BITSHUFFLE)
    root.create_dataset(
        "0",
        data=data,
        chunks=chunks,
        compressor=compressor,
        overwrite=True,
    )

    root.attrs.update(
        {
            "multiscales": [
                {
                    "version": "0.4",
                    "name": output_path.stem,
                    "axes": [
                        {"name": "c", "type": "channel"},
                        {"name": "z", "type": "space"},
                        {"name": "y", "type": "space"},
                        {"name": "x", "type": "space"},
                    ],
                    "datasets": [
                        {
                            "path": "0",
                            "coordinateTransformations": [
                                {
                                    "type": "scale",
                                    "scale": [
                                        1.0,
                                        float(scale.get("z", 1.0)),
                                        float(scale.get("y", 1.0)),
                                        float(scale.get("x", 1.0)),
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ],
            "omero": {
                "channels": [
                    {
                        "label": channel.get("remapped_name") or channel.get("name"),
                    }
                    for channel in channels
                ]
            },
        }
    )

    LOGGER.info("OME-Zarr dataset written to %s", output_path)
    return output_path


__all__ = [
    "IngestError",
    "extract_metadata",
    "convert_to_ome_zarr",
    "load_panel_mapping",
]
