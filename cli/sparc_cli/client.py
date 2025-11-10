"""HTTP client for communicating with the Sparc API."""

from __future__ import annotations

import logging
import os
from typing import Any, Mapping

import requests

from .config import RunConfig

_LOGGER = logging.getLogger(__name__)


class ApiError(RuntimeError):
    """Raised when the API returns an error response."""


class ApiClient:
    """Simple HTTP client for interacting with the Sparc platform API."""

    def __init__(self, base_url: str | None = None, *, timeout: float = 30.0) -> None:
        self.base_url = base_url or os.environ.get(
            "SPARC_API_URL", "http://localhost:8000"
        )
        self.timeout = timeout

    def submit_ingest(self, config: RunConfig) -> Mapping[str, Any]:
        """Submit an ingest request to the backend."""

        url = f"{self.base_url.rstrip('/')}/ingest"
        payload = config.payload
        _LOGGER.debug("Submitting ingest request to %s with payload %s", url, payload)
        try:
            response = requests.post(url, json=payload, timeout=self.timeout)
        except requests.RequestException as exc:  # pragma: no cover - network errors
            raise ApiError("Failed to submit request to API") from exc

        if response.status_code >= 400:
            _LOGGER.error(
                "API returned error %s: %s", response.status_code, response.text
            )
            raise ApiError(
                f"API returned error {response.status_code}: {response.text}"
            )

        try:
            data = response.json()
        except ValueError as exc:  # pragma: no cover - unexpected API payloads
            raise ApiError("API response was not valid JSON") from exc

        _LOGGER.info(
            "Ingest task %s created for project %s",
            data.get("task_id"),
            payload.get("project_slug"),
        )
        return data


__all__ = ["ApiClient", "ApiError"]
