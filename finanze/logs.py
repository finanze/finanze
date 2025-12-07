import logging
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

LOG_FILENAME = "finanze.log"


class TZFormatter(logging.Formatter):
    def formatTime(self, record, datefmt: Optional[str] = None):
        ct = time.localtime(record.created)
        if datefmt:
            s = time.strftime(datefmt, ct)
        else:
            s = time.strftime("%Y-%m-%d %H:%M:%S%z", ct)
        return s

    def format(self, record):
        original_levelname = record.levelname
        record.levelname = record.levelname[0]
        result = super().format(record)
        record.levelname = original_levelname
        return result


_THIRD_PARTY_LOGGERS = [
    "waitress",
    "waitress.queue",
    "urllib3",
    "requests",
    "selenium",
]


def _apply_third_party_level(level_name: str):
    if level_name == "NONE":
        return
    lvl = logging.getLevelName(level_name)
    for name in _THIRD_PARTY_LOGGERS:
        logging.getLogger(name).setLevel(lvl)


def configure_logging(args):
    root_logger = logging.getLogger()
    if root_logger.handlers:
        for h in root_logger.handlers:
            root_logger.removeHandler(h)

    console_level_name = args.log_level
    console_enabled = console_level_name != "NONE"

    file_level_name = args.log_file_level if args.log_file_level else console_level_name
    file_enabled = file_level_name != "NONE"

    console_level = (
        logging.getLevelName(console_level_name)
        if console_enabled
        else logging.CRITICAL + 1
    )
    file_level = (
        logging.getLevelName(file_level_name) if file_enabled else logging.CRITICAL + 1
    )

    fmt = "%(asctime)s | %(levelname)s | %(name)s:%(lineno)d | %(message)s"
    formatter = TZFormatter(fmt)

    if console_enabled:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(console_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    log_file_path = None
    if file_enabled:
        log_file_path = Path(args.log_dir) / LOG_FILENAME

        try:
            log_file_path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                log_file_path, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
            )
            file_handler.setLevel(file_level)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        except OSError as e:
            logging.getLogger(__name__).warning(
                f"Failed to set up file logging at {log_file_path}: {e}. Continuing without file logging."
            )
            file_enabled = False

    active_levels = [
        lvl
        for lvl in [
            console_level if console_enabled else None,
            file_level if file_enabled else None,
        ]
        if lvl is not None
    ]
    root_logger.setLevel(min(active_levels) if active_levels else logging.INFO)

    _apply_third_party_level(
        args.third_party_log_level if hasattr(args, "third_party_log_level") else "NONE"
    )

    logging.getLogger(__name__).info(
        f"Logging configured. Console={'DISABLED' if not console_enabled else console_level_name}, File={'DISABLED' if not file_enabled else file_level_name}, FilePath={log_file_path} ThirdParty={args.third_party_log_level}"
    )

    return log_file_path
