"""Background worker placeholder implementation."""

from __future__ import annotations

import asyncio
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s - %(message)s")
LOGGER = logging.getLogger(__name__)


async def main() -> None:
    """Run the worker loop."""

    LOGGER.info("Worker started")
    while True:  # pragma: no cover - long-running worker loop
        LOGGER.debug("Waiting for work...")
        await asyncio.sleep(10)


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
