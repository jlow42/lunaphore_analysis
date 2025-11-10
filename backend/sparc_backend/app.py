"""Placeholder FastAPI application for the Sparc backend."""

from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(title="Sparc API")


@app.get("/healthz")
async def healthcheck() -> dict[str, str]:
    """Health check endpoint."""

    return {"status": "ok"}
