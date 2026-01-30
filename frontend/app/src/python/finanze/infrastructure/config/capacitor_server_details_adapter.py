from application.ports.server_details_port import ServerDetailsPort
from domain.platform import OS
from domain.status import BackendDetails, BackendOptions


def _resolve_version() -> str:
    try:
        from version import __version__

        if __version__:
            return str(__version__)
    except Exception:
        pass
    return "0.0.0"


class CapacitorServerDetailsAdapter(ServerDetailsPort):
    def __init__(self, operative_system: OS):
        self._os = operative_system

    async def get_backend_details(self) -> BackendDetails:
        return BackendDetails(
            version=_resolve_version(), options=BackendOptions(), platform_type=self._os
        )

    def get_os(self) -> OS:
        return self._os
