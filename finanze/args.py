import argparse
import logging
import os
from logging import getLevelName

import appdirs

DEFAULT_DATA_DIR = os.path.join(os.getcwd(), "finanze")


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
        help="Set the logging level.",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
    )

    return parser


def parse_args() -> argparse.Namespace:
    parser = app_args()
    args = parser.parse_args()

    os.makedirs(args.data_dir, exist_ok=True)

    args.credentials_storage_mode = os.environ.get("CREDENTIAL_STORAGE", "DB")
    args.logged_username = os.environ.get("USERNAME")
    args.logged_password = os.environ.get("PASSWORD")

    logging.basicConfig(level=getLevelName(args.log_level))
    logging.getLogger().setLevel(getLevelName(args.log_level))

    logging.info(f"Logging level set to: {args.log_level}")
    logging.info(f"Using data directory: {args.data_dir}")

    return args
