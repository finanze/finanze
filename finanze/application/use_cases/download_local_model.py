from typing import Optional

from application.ports.external_integration_port import ExternalIntegrationPort
from application.ports.huggingface_catalog import HuggingFaceCatalog
from application.ports.local_model_catalog import LocalModelCatalog
from application.ports.local_model_router import LocalModelRouter
from application.ports.local_model_runtime import LocalModelRuntime
from domain.exception.exceptions import (
    ExternalIntegrationRequired,
    LocalModelError,
    LocalModelErrorCode,
)
from domain.external_integration import ExternalIntegrationId
from domain.local_model import (
    DownloadLocalModelRequest,
    HuggingFaceModelKind,
    LocalModelState,
    LocalRuntimeMode,
    hugging_face_model_id,
)
from domain.use_cases.download_local_model import DownloadLocalModel

FREE_SPACE_MARGIN = 512 * 1024 * 1024
ACTIVE_STATES = {
    LocalModelState.LOADED,
    LocalModelState.LOADING,
    LocalModelState.SLEEPING,
}


class DownloadLocalModelImpl(DownloadLocalModel):
    def __init__(
        self,
        external_integration_port: ExternalIntegrationPort,
        runtime: LocalModelRuntime,
        router: LocalModelRouter,
        catalog: LocalModelCatalog,
        hugging_face: HuggingFaceCatalog,
    ):
        self._external_integration_port = external_integration_port
        self._runtime = runtime
        self._router = router
        self._catalog = catalog
        self._hugging_face = hugging_face

    async def execute(self, request: DownloadLocalModelRequest):
        payload = await self._external_integration_port.get_payload(
            ExternalIntegrationId.LOCAL_MODELS
        )
        if payload is None:
            raise ExternalIntegrationRequired([ExternalIntegrationId.LOCAL_MODELS])

        size: Optional[int] = None
        vision_size: Optional[int] = None
        if request.catalog_id:
            entry = self._catalog.find(request.catalog_id)
            if entry is None:
                raise LocalModelError(LocalModelErrorCode.MODEL_NOT_FOUND)
            model_id, size, vision_size = entry.id, entry.size, entry.vision_size
        else:
            model_id = hugging_face_model_id(request.repo, request.quant)

        connection = await self._runtime.resolve(payload)
        router_models = await self._router.list_models(connection)
        existing = next(
            (
                model
                for model in router_models
                if model.id.casefold() == model_id.casefold()
                and model.state != LocalModelState.INCOMPLETE
            ),
            None,
        )
        if existing is not None and (
            not request.vision
            or existing.vision
            or existing.has_mmproj
            or existing.state == LocalModelState.DOWNLOADING
        ):
            return

        if size is None:
            size, vision_size = await self._quant_sizes(request.repo, request.quant)
        if request.vision and not vision_size:
            raise LocalModelError(
                LocalModelErrorCode.INVALID_MODEL, "No vision projector available"
            )

        needed = vision_size if existing is not None else size
        if request.vision and existing is None:
            needed += vision_size
        if connection.mode == LocalRuntimeMode.BUILT_IN:
            free = self._runtime.free_space()
            if free is not None and free < needed + FREE_SPACE_MARGIN:
                raise LocalModelError(LocalModelErrorCode.INSUFFICIENT_SPACE)

        if existing is not None:
            model_id = existing.id
            if existing.state in ACTIVE_STATES:
                await self._router.unload(connection, model_id)
        await self._router.download(connection, model_id, vision=request.vision)

    async def _quant_sizes(self, repo: str, quant: str) -> tuple[int, Optional[int]]:
        quants = await self._hugging_face.list_quants(repo)
        if quants.kind == HuggingFaceModelKind.ENCODER:
            raise LocalModelError(LocalModelErrorCode.UNSUPPORTED_MODEL)
        option = next(
            (q for q in quants.quants if q.quant.casefold() == quant.casefold()), None
        )
        if option is None:
            raise LocalModelError(LocalModelErrorCode.INVALID_MODEL)
        return option.size or 0, option.vision_size
