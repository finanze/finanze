import asyncio
import logging
import sys
import traceback

from args import parse_args
from infrastructure.config.server_details_adapter import _resolve_version
from server import FinanzeServer

log = logging.getLogger(__name__)


def main() -> None:
    try:
        args = parse_args()

        log.info(f"Initializing Finanze server v{_resolve_version()}...")
        server = FinanzeServer(args)

        asyncio.run(server.run())

    except ImportError as e:
        log.critical(f"ImportError: {e}\n{traceback.format_exc()}")
        sys.exit(1)
    except KeyboardInterrupt:
        log.info("Received keyboard interrupt. Shutting down...")
    except Exception as e:
        log.critical(f"Unexpected error: {e}\n{traceback.format_exc()}")
    finally:
        logging.info("Application exiting.")


if __name__ == "__main__":
    main()
