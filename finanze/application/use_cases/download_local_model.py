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
    LocalRuntimeMode,
    hugging_face_model_id,
)
from domain.use_cases.download_local_model import DownloadLocalModel

FREE_SPACE_MARGIN = 512 * 1024 * 1024


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
        if request.catalog_id:
            entry = self._catalog.find(request.catalog_id)
            if entry is None:
                raise LocalModelError(LocalModelErrorCode.MODEL_NOT_FOUND)
            model_id, size = entry.id, entry.size
        else:
            model_id = hugging_face_model_id(request.repo, request.quant)

        connection = await self._runtime.resolve(payload)
        router_models = await self._router.list_models(connection)
        if any(model.id.casefold() == model_id.casefold() for model in router_models):
            return

        if size is None:
            size = await self._quant_size(request.repo, request.quant)

        if connection.mode == LocalRuntimeMode.BUILT_IN:
            free = self._runtime.free_space()
            if free is not None and free < size + FREE_SPACE_MARGIN:
                raise LocalModelError(LocalModelErrorCode.INSUFFICIENT_SPACE)

        await self._router.download(connection, model_id)

    async def _quant_size(self, repo: str, quant: str) -> int:
        quants = await self._hugging_face.list_quants(repo)
        if quants.kind == HuggingFaceModelKind.ENCODER:
            raise LocalModelError(LocalModelErrorCode.UNSUPPORTED_MODEL)
        option = next(
            (q for q in quants.quants if q.quant.casefold() == quant.casefold()), None
        )
        if option is None:
            raise LocalModelError(LocalModelErrorCode.INVALID_MODEL)
        return option.size or 0
