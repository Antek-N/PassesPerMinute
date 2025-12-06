import logging
import sys

from passes_per_minute.app import run
from passes_per_minute.logging_config import configure_logging


def main() -> int:
    """
    Main entry point for PassesPerMinute.

    Configures logging, launches the data processing pipeline,
    and returns an appropriate exit code.
    """
    configure_logging()
    log = logging.getLogger(__name__)
    log.debug("Logging configured")

    log.info("Launching PassesPerMinute pipeline")

    # Run the main process and return its exit code
    return run()


if __name__ == "__main__":
    sys.exit(main())
