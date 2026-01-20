from application.ports.server_details_port import ServerDetailsPort
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
    async def get_backend_details(self) -> BackendDetails:
        return BackendDetails(version=_resolve_version(), options=BackendOptions())
