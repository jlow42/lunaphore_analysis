"""CLI entry point for the ``sparc`` command."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .client import ApiClient, ApiError
from .config import RunConfig, load_config

_LOGGER = logging.getLogger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sparc platform command-line interface")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Submit an analysis job")
    run_parser.add_argument(
        "--config",
        dest="config",
        type=Path,
        required=True,
        help="Path to the run configuration file (YAML or JSON)",
    )

    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging verbosity (DEBUG, INFO, WARNING, ERROR)",
    )

    parser.add_argument(
        "--api-url",
        dest="api_url",
        default=None,
        help="Override the API base URL",
    )

    return parser


def configure_logging(level: str) -> None:
    """Configure root logger for console output."""

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(levelname)s %(name)s - %(message)s",
    )


def handle_run(config_path: Path, api_url: str | None) -> int:
    """Handle ``sparc run`` commands."""

    _LOGGER.debug("Loading configuration from %s", config_path)
    run_config: RunConfig
    try:
        run_config = load_config(config_path)
    except (FileNotFoundError, ValueError) as exc:
        _LOGGER.error("Failed to load configuration: %s", exc)
        return 1

    client = ApiClient(base_url=api_url)
    try:
        job_id = client.submit_job(run_config.payload)
    except ApiError as exc:
        _LOGGER.error("Job submission failed: %s", exc)
        return 2

    _LOGGER.info("Job submitted successfully with id %s", job_id)
    return 0


def main(argv: list[str] | None = None) -> int:
    """Entry point for the ``sparc`` CLI."""

    parser = _build_parser()
    args = parser.parse_args(argv)

    configure_logging(args.log_level)
    _LOGGER.debug("CLI arguments: %%s", args)

    if args.command == "run":
        return handle_run(args.config, args.api_url)

    parser.print_help()
    return 1


if __name__ == "__main__":  # pragma: no cover - manual invocation
    sys.exit(main())
