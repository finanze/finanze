from application.ports.external_integration_port import ExternalIntegrationPort
from application.ports.local_model_imports import LocalModelImports
from application.ports.local_model_router import LocalModelRouter
from application.ports.local_model_runtime import LocalModelRuntime
from domain.exception.exceptions import (
    ExternalIntegrationRequired,
    LocalModelError,
    LocalModelErrorCode,
)
from domain.external_integration import ExternalIntegrationId
from domain.local_model import (
    ImportedLocalModel,
    ImportLocalModelRequest,
    LocalRuntimeMode,
)
from domain.use_cases.import_local_model import ImportLocalModel


class ImportLocalModelImpl(ImportLocalModel):
    def __init__(
        self,
        external_integration_port: ExternalIntegrationPort,
        runtime: LocalModelRuntime,
        router: LocalModelRouter,
        imports: LocalModelImports,
    ):
        self._external_integration_port = external_integration_port
        self._runtime = runtime
        self._router = router
        self._imports = imports

    async def execute(self, request: ImportLocalModelRequest) -> ImportedLocalModel:
        payload = await self._external_integration_port.get_payload(
            ExternalIntegrationId.LOCAL_MODELS
        )
        if payload is None:
            raise ExternalIntegrationRequired([ExternalIntegrationId.LOCAL_MODELS])

        connection = await self._runtime.resolve(payload)
        if connection.mode != LocalRuntimeMode.BUILT_IN:
            raise LocalModelError(LocalModelErrorCode.IMPORT_UNSUPPORTED)

        imported = await self._imports.add(request.path)
        await self._router.list_models(connection, reload=True)
        return imported
