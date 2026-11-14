from typing import Optional

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
    LocalRouterConnection,
    LocalRouterModel,
    LocalRuntimeMode,
    is_hugging_face_model_id,
    is_imported_model_id,
    model_id_repo,
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
        models = await self._router.list_models(connection)
        model = _find(models, model_id)

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

        if request.vision_only:
            if not model.has_mmproj:
                raise LocalModelError(LocalModelErrorCode.MODEL_NOT_FOUND)
            await self._remove_vision(connection, models, model_id)
            return

        if model.state == LocalModelState.DOWNLOADING:
            await self._cancel_download(connection, model_id)
            return

        repo = model_id_repo(model_id)
        shared = any(
            other.id != model_id
            and other.state != LocalModelState.INCOMPLETE
            and model_id_repo(other.id).casefold() == repo.casefold()
            for other in models
        )
        if (
            model.has_mmproj
            and model.state != LocalModelState.INCOMPLETE
            and repo
            and not shared
        ):
            if model.state in ACTIVE_STATES:
                await self._router.unload(connection, model_id)
            await self._router.delete_vision(connection, model_id)
        await self._router.delete(connection, model_id)

    async def _remove_vision(
        self,
        connection: LocalRouterConnection,
        models: list[LocalRouterModel],
        model_id: str,
    ):
        repo = model_id_repo(model_id).casefold()
        for model in models:
            same_repo = model.id == model_id or (
                bool(repo) and model_id_repo(model.id).casefold() == repo
            )
            if same_repo and model.state in ACTIVE_STATES:
                await self._router.unload(connection, model.id)
        await self._router.delete_vision(connection, model_id)
        await self._router.list_models(connection, reload=True)

    # Deleting a downloading model also deletes its finished files, so cancel first
    async def _cancel_download(self, connection: LocalRouterConnection, model_id: str):
        await self._router.unload(connection, model_id)
        model = _find(await self._router.list_models(connection, reload=True), model_id)
        if model is None:
            return
        if model.state == LocalModelState.INCOMPLETE:
            await self._router.delete(connection, model_id)
            return
        await self._router.delete_vision(connection, model_id)
        await self._router.list_models(connection, reload=True)


def _find(models: list[LocalRouterModel], model_id: str) -> Optional[LocalRouterModel]:
    return next((m for m in models if m.id == model_id), None)
