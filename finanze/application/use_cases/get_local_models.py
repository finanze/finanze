import logging

from application.ports.external_integration_port import ExternalIntegrationPort
from application.ports.local_model_catalog import LocalModelCatalog
from application.ports.local_model_imports import LocalModelImports
from application.ports.local_model_router import LocalModelRouter
from application.ports.local_model_runtime import LocalModelRuntime
from domain.exception.exceptions import LocalModelError
from domain.external_integration import ExternalIntegrationId
from domain.local_model import (
    IMPORTED_MODEL_PREFIX,
    ImportedLocalModel,
    LocalModel,
    LocalModelSource,
    LocalModelState,
    LocalModelsOverview,
    LocalRouterModel,
    LocalRuntimeMode,
    is_hugging_face_model_id,
)
from domain.use_cases.get_local_models import GetLocalModels


class GetLocalModelsImpl(GetLocalModels):
    def __init__(
        self,
        external_integration_port: ExternalIntegrationPort,
        runtime: LocalModelRuntime,
        router: LocalModelRouter,
        imports: LocalModelImports,
        catalog: LocalModelCatalog,
    ):
        self._external_integration_port = external_integration_port
        self._runtime = runtime
        self._router = router
        self._imports = imports
        self._catalog = catalog
        self._log = logging.getLogger(__name__)

    async def execute(self, refresh: bool = False) -> LocalModelsOverview:
        overview = LocalModelsOverview(
            connected=False,
            capabilities=self._runtime.capabilities(),
            catalog=self._catalog.entries(),
        )
        payload = await self._external_integration_port.get_payload(
            ExternalIntegrationId.LOCAL_MODELS
        )
        if payload is None:
            return overview
        overview.connected = True

        try:
            connection = await self._runtime.resolve(payload)
            overview.mode = connection.mode
            overview.source = connection.source
            overview.server_url = (
                None
                if connection.mode == LocalRuntimeMode.BUILT_IN
                else connection.base_url
            )
            built_in = connection.mode == LocalRuntimeMode.BUILT_IN
            imported: list[ImportedLocalModel] = []
            if built_in:
                if refresh:
                    await self._imports.sync()
                imported = await self._imports.list()
                overview.models_folder = self._imports.folder()
            router_models = await self._router.list_models(connection, reload=refresh)
        except LocalModelError as e:
            self._log.warning(f"Could not list local models: {e.code.value}")
            overview.error = e.code
            return overview

        overview.reachable = True
        overview.models = self._merge(router_models, imported, built_in)
        return overview

    def _merge(
        self,
        router_models: list[LocalRouterModel],
        imported: list[ImportedLocalModel],
        built_in: bool,
    ) -> list[LocalModel]:
        imported_by_id = {model.id: model for model in imported}
        models = [
            self._to_model(model, imported_by_id, built_in) for model in router_models
        ]
        listed = {model.id for model in router_models}
        models += [
            LocalModel(
                id=model.id,
                name=model.id[len(IMPORTED_MODEL_PREFIX) :],
                source=LocalModelSource.IMPORTED,
                state=LocalModelState.MISSING,
                deletable=True,
                path=model.path,
            )
            for model in imported
            if not model.exists and model.id not in listed
        ]
        return sorted(models, key=lambda model: model.name.casefold())

    def _to_model(
        self,
        model: LocalRouterModel,
        imported_by_id: dict[str, ImportedLocalModel],
        built_in: bool,
    ) -> LocalModel:
        entry = self._catalog.find(model.id)
        imported = imported_by_id.get(model.id)
        cached = (
            model.removable
            if model.removable is not None
            else is_hugging_face_model_id(model.id)
        )
        size = model.size
        if imported is not None:
            source = LocalModelSource.IMPORTED
            name = model.id[len(IMPORTED_MODEL_PREFIX) :]
            deletable = built_in
            size = size or imported.size
        elif entry is not None:
            source = LocalModelSource.CATALOG
            name = entry.name
            deletable = cached
            size = size or entry.size
        elif cached:
            source = LocalModelSource.HUGGING_FACE
            name = model.id
            deletable = True
        else:
            source = LocalModelSource.SERVER
            name = model.id
            deletable = False
        state = model.state
        if imported is not None and not imported.exists:
            state = LocalModelState.MISSING
        return LocalModel(
            id=model.id,
            name=name,
            source=source,
            state=state,
            size=size,
            downloaded=model.downloaded,
            decisions=model.decisions or bool(entry and entry.decisions),
            deletable=deletable,
            path=imported.path if imported is not None and built_in else None,
        )
