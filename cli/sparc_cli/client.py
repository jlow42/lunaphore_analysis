"""HTTP client for communicating with the Sparc API."""

from __future__ import annotations

import logging
import os
from typing import Any, Mapping

import requests

_LOGGER = logging.getLogger(__name__)


class ApiError(RuntimeError):
    """Raised when the API returns an error response."""


class ApiClient:
    """Simple HTTP client for interacting with the Sparc platform API."""

    def __init__(self, base_url: str | None = None, *, timeout: float = 10.0) -> None:
        self.base_url = base_url or os.environ.get("SPARC_API_URL", "http://localhost:8000")
        self.timeout = timeout

    def submit_job(self, payload: Mapping[str, Any]) -> str:
        """Submit an analysis job to the API.

        Args:
            payload: Mapping of job parameters to submit to the backend.

        Raises:
            ApiError: If the API request fails.

        Returns:
            The job identifier returned by the API.
        """

        url = f"{self.base_url.rstrip('/')}/jobs"
        _LOGGER.debug("Submitting job to %s", url)
        try:
            response = requests.post(url, json=payload, timeout=self.timeout)
        except requests.RequestException as exc:  # pragma: no cover - network errors
            raise ApiError("Failed to submit job to API") from exc

        if response.status_code >= 400:
            _LOGGER.error("API returned error %s: %s", response.status_code, response.text)
            raise ApiError(f"API returned error {response.status_code}: {response.text}")

        try:
            data = response.json()
        except ValueError as exc:
            raise ApiError("API response was not valid JSON") from exc

        job_id = data.get("job_id")
        if not job_id:
            raise ApiError("API response did not include a job identifier")

        _LOGGER.info("Submitted job %s", job_id)
        return str(job_id)
