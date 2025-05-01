import argparse
import logging
import os
from logging import getLevelName

DEFAULT_DATA_DIR = os.path.join(os.getcwd(), "finanze_data")
DEFAULT_DB_NAME = "finanze_data.db"
DEFAULT_CONFIG_NAME = "config.yml"


def app_args() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Finanze Backend Server")

    parser.add_argument(
        "--data-dir",
        help="Directory to store database and configuration files.",
        type=str,
        default=DEFAULT_DATA_DIR,
    )
    parser.add_argument(
        "--port",
        help="Port on which the API server will run.",
        type=int,
        default=8080,
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

    args.db_path = os.path.join(args.data_dir, DEFAULT_DB_NAME)
    args.config_path = os.path.join(args.data_dir, DEFAULT_CONFIG_NAME)
    args.credentials_storage_mode = os.environ.get("CREDENTIAL_STORAGE", "DB")
    args.db_password = os.environ.get("DB_CIPHER_PASSWORD")

    logging.basicConfig(level=getLevelName(args.log_level))
    logging.getLogger().setLevel(getLevelName(args.log_level))

    logging.info(f"Logging level set to: {args.log_level}")
    logging.info(f"Using data directory: {args.data_dir}")
    logging.info(f"Database path: {args.db_path}")
    logging.info(f"Config path: {args.config_path}")

    return args
