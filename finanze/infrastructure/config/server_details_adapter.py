import platform
from argparse import Namespace
from pathlib import Path
from typing import Optional

from application.ports.server_details_port import ServerDetailsPort
from domain.platform import OS
from domain.status import BackendDetails, BackendLogLevel, BackendOptions


def _resolve_version() -> str:
    try:
        from version import __version__

        if __version__:
            return str(__version__)
    except Exception:
        pass
    return "0.0.0"


def _detect_os() -> OS | None:
    system = platform.system().upper()

    if system == "DARWIN":
        return OS.MACOS
    elif system == "WINDOWS":
        return OS.WINDOWS
    elif system == "LINUX":
        return OS.LINUX

    return None


class ServerDetailsAdapter(ServerDetailsPort):
    def __init__(self, args: Namespace):
        self._os = _detect_os()
        self._args = args

    async def get_backend_details(self) -> BackendDetails:
        options = self._build_options()
        return BackendDetails(
            version=_resolve_version(), options=options, platform_type=self._os
        )

    def _build_options(self) -> BackendOptions:
        data_dir = getattr(self._args, "data_dir", None)
        log_dir = getattr(self._args, "log_dir", None)
        return BackendOptions(
            data_dir=str(Path(data_dir).resolve()) if data_dir else None,
            port=getattr(self._args, "port", None),
            log_level=self._to_log_level(getattr(self._args, "log_level", None)),
            log_dir=str(Path(log_dir).resolve()) if log_dir else None,
            log_file_level=self._to_log_level(
                getattr(self._args, "log_file_level", None)
            ),
            third_party_log_level=self._to_log_level(
                getattr(self._args, "third_party_log_level", None)
            ),
        )

    def get_os(self) -> OS:
        return self._os

    @staticmethod
    def _to_log_level(level_name: Optional[str]) -> Optional[BackendLogLevel]:
        if not level_name:
            return None
        try:
            return BackendLogLevel(level_name)
        except ValueError:
            return None
