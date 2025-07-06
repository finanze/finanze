import logging
import sys
import traceback

from args import parse_args
from server import FinanzeServer

log = logging.getLogger(__name__)


def main() -> None:
    server = None
    try:
        args = parse_args()

        log.info("Initializing Finanze server...")
        server = FinanzeServer(args)

        server.run()

    except ImportError as e:
        log.critical(f"ImportError: {e}\n{traceback.format_exc()}")
        sys.exit(1)
    except Exception as e:
        log.critical(f"Unexpected error: {e}\n{traceback.format_exc()}")
    finally:
        logging.info("Application exiting.")


if __name__ == "__main__":
    main()
