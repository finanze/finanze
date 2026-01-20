import logging
import sys


_THIRD_PARTY_LOGGERS = [
    "urllib3",
    "requests",
]


def _get_attr(obj, name: str, default=None):
    return getattr(obj, name, default) if obj is not None else default


def _apply_third_party_level(level_name: str):
    if not level_name or level_name == "NONE":
        return
    lvl = logging.getLevelName(level_name)
    for name in _THIRD_PARTY_LOGGERS:
        logging.getLogger(name).setLevel(lvl)


def configure_logging(args=None, *, default_level: str = "INFO"):
    root_logger = logging.getLogger()
    if root_logger.handlers:
        for h in list(root_logger.handlers):
            root_logger.removeHandler(h)

    console_level_name = _get_attr(args, "log_level", None) or default_level
    if console_level_name == "NONE":
        console_level_name = "INFO"

    level = logging.getLevelName(console_level_name)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s:%(lineno)d | %(message)s"
        )
    )

    root_logger.addHandler(handler)
    root_logger.setLevel(level)

    third_party_level = _get_attr(args, "third_party_log_level", "NONE")
    _apply_third_party_level(third_party_level)

    logging.getLogger(__name__).info(
        f"Logging configured. Console={console_level_name} ThirdParty={third_party_level}"
    )

    return None
