import argparse
import logging
import os
from pathlib import Path

import appdirs
from logs import configure_logging


def app_args() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Finanze Server")

    parser.add_argument(
        "--data-dir",
        help="Directory to store database and configuration files.",
        type=str,
        default=appdirs.user_data_dir("Finanze", False),
    )
    parser.add_argument(
        "--port",
        help="Port on which the API server will run.",
        type=int,
        default=7592,
    )
    parser.add_argument(
        "--log-level",
        help="Set the console logging level (use NONE to disable console logging).",
        choices=["NONE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
    )
    parser.add_argument(
        "--log-file",
        help="Path to log file (default: <data-dir>/logs/finanze.log).",
        type=str,
        default=None,
    )
    parser.add_argument(
        "--log-file-level",
        help="Set the file logging level (default: same as --log-level; if console is NONE then INFO; use NONE to disable file logging).",
        choices=["NONE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default=None,
    )
    parser.add_argument(
        "--third-party-log-level",
        help="Logging level for third-party libraries (waitress, urllib3, requests, selenium). Use NONE to leave unchanged.",
        choices=["NONE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="ERROR",
    )
    return parser


def parse_args() -> argparse.Namespace:
    parser = app_args()
    args = parser.parse_args()

    args.data_dir = Path(args.data_dir)
    os.makedirs(args.data_dir, exist_ok=True)

    args.credentials_storage_mode = os.environ.get("CREDENTIAL_STORAGE", "DB")
    args.logged_username = os.environ.get("USERNAME")
    args.logged_password = os.environ.get("PASSWORD")

    configure_logging(args)
    logging.info(f"Using data directory: {args.data_dir}")

    return args
