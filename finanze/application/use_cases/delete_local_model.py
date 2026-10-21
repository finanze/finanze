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
    LocalModelRequest,
    LocalModelState,
    LocalRuntimeMode,
    is_hugging_face_model_id,
    is_imported_model_id,
)
from domain.use_cases.delete_local_model import DeleteLocalModel

ACTIVE_STATES = {
    LocalModelState.LOADED,
    LocalModelState.LOADING,
    LocalModelState.SLEEPING,
}


class DeleteLocalModelImpl(DeleteLocalModel):
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

    async def execute(self, request: LocalModelRequest):
        payload = await self._external_integration_port.get_payload(
            ExternalIntegrationId.LOCAL_MODELS
        )
        if payload is None:
            raise ExternalIntegrationRequired([ExternalIntegrationId.LOCAL_MODELS])

        model_id = request.model_id
        connection = await self._runtime.resolve(payload)
        built_in = connection.mode == LocalRuntimeMode.BUILT_IN
        model = next(
            (m for m in await self._router.list_models(connection) if m.id == model_id),
            None,
        )

        if built_in and is_imported_model_id(model_id):
            if model is not None and model.state in ACTIVE_STATES:
                await self._router.unload(connection, model_id)
            if not await self._imports.remove(model_id):
                raise LocalModelError(LocalModelErrorCode.MODEL_NOT_FOUND)
            await self._router.list_models(connection, reload=True)
            return

        if model is None:
            raise LocalModelError(LocalModelErrorCode.MODEL_NOT_FOUND)
        removable = (
            model.removable
            if model.removable is not None
            else is_hugging_face_model_id(model_id)
        )
        if not removable:
            raise LocalModelError(LocalModelErrorCode.NOT_DELETABLE)

        await self._router.delete(connection, model_id)
