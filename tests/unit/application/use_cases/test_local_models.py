from unittest.mock import AsyncMock, MagicMock

import pytest
from application.ports.local_model_catalog import LocalModelCatalog
from application.use_cases.delete_local_model import DeleteLocalModelImpl
from application.use_cases.download_local_model import (
    FREE_SPACE_MARGIN,
    DownloadLocalModelImpl,
)
from application.use_cases.get_external_labeling_models import (
    GetExternalLabelingModelsImpl,
)
from application.use_cases.get_local_models import GetLocalModelsImpl
from application.use_cases.import_local_model import ImportLocalModelImpl
from application.use_cases.list_hugging_face_quants import ListHuggingFaceQuantsImpl
from domain.exception.exceptions import (
    ExternalIntegrationRequired,
    IntegrationNotFound,
    LocalModelError,
    LocalModelErrorCode,
)
from domain.external_integration import ExternalIntegrationId
from domain.external_labeling import ExternalLabelingModel
from domain.local_model import (
    DownloadLocalModelRequest,
    HuggingFaceModelKind,
    HuggingFaceQuantOption,
    HuggingFaceQuants,
    ImportedLocalModel,
    ImportLocalModelRequest,
    LocalModelCatalogEntry,
    LocalModelRequest,
    LocalModelsCapabilities,
    LocalModelSource,
    LocalModelState,
    LocalRouterConnection,
    LocalRouterModel,
    LocalRuntimeMode,
    LocalRuntimeSource,
)

BUILT_IN = LocalRouterConnection(
    base_url="http://127.0.0.1:5000",
    api_key="generated",
    mode=LocalRuntimeMode.BUILT_IN,
    source=LocalRuntimeSource.BUILT_IN,
)
EXTERNAL = LocalRouterConnection(
    base_url="http://server:8080",
    mode=LocalRuntimeMode.EXTERNAL,
    source=LocalRuntimeSource.PAYLOAD,
)
CATALOG_ID = "ggml-org/Laya-GGUF:Q8_0"
ENTRY = LocalModelCatalogEntry(
    id=CATALOG_ID,
    name="Laya",
    repo="ggml-org/Laya-GGUF",
    quant="Q8_0",
    size=1000,
    ram=2000,
    params="0.4B",
    license="apache-2.0",
    decisions=True,
)
CAPABILITIES = LocalModelsCapabilities(built_in_available=True, can_import_files=True)


class FakeCatalog(LocalModelCatalog):
    def entries(self):
        return [ENTRY]


class FakeRuntime:
    def __init__(self, connection=BUILT_IN, error=None, free=None):
        self.connection = connection
        self.error = error
        self.free = free
        self.resolved = 0

    def capabilities(self):
        return CAPABILITIES

    async def resolve(self, credentials):
        self.resolved += 1
        if self.error:
            raise self.error
        return self.connection

    async def stop(self):
        pass

    def free_space(self):
        return self.free


class FakeRouter:
    def __init__(self, models=None, error=None):
        self.models = models or []
        self.error = error
        self.list_calls: list[bool] = []
        self.downloads: list[str] = []
        self.deleted: list[str] = []
        self.unloaded: list[str] = []

    async def list_models(self, connection, reload=False):
        self.list_calls.append(reload)
        if self.error:
            raise self.error
        return self.models

    async def download(self, connection, model_id):
        self.downloads.append(model_id)

    async def delete(self, connection, model_id):
        self.deleted.append(model_id)

    async def unload(self, connection, model_id):
        self.unloaded.append(model_id)


class FakeImports:
    def __init__(self, models=None, removable=True):
        self.models = models or []
        self.removable = removable
        self.synced = 0
        self.added: list[str] = []
        self.removed: list[str] = []

    def folder(self):
        return "/models/local"

    async def list(self):
        return self.models

    async def add(self, path):
        self.added.append(path)
        return ImportedLocalModel(id="local/model", path=path, size=10)

    async def remove(self, model_id):
        self.removed.append(model_id)
        return self.removable

    async def sync(self):
        self.synced += 1


def _integrations(payload=None) -> AsyncMock:
    port = AsyncMock()
    port.get_payload.return_value = payload
    return port


def _model(model_id, state=LocalModelState.UNLOADED, **kwargs) -> LocalRouterModel:
    return LocalRouterModel(id=model_id, state=state, **kwargs)


class TestGetLocalModels:
    def _use_case(self, payload, runtime=None, router=None, imports=None):
        return GetLocalModelsImpl(
            _integrations(payload),
            runtime or FakeRuntime(),
            router or FakeRouter(),
            imports or FakeImports(),
            FakeCatalog(),
        )

    @pytest.mark.asyncio
    async def test_not_connected_does_not_start_runtime(self):
        runtime = FakeRuntime()
        overview = await self._use_case(None, runtime=runtime).execute()
        assert overview.connected is False
        assert overview.capabilities == CAPABILITIES
        assert overview.catalog == [ENTRY]
        assert overview.models == []
        assert runtime.resolved == 0

    @pytest.mark.asyncio
    async def test_built_in_merges_models(self):
        router = FakeRouter(
            [
                _model(CATALOG_ID, LocalModelState.LOADED),
                _model(
                    "org/new-GGUF:Q4_K_M", LocalModelState.DOWNLOADING, downloaded=5
                ),
                _model("local/mine", size=None),
                _model("local/gone"),
                _model("server-model", removable=False),
            ]
        )
        imports = FakeImports(
            [
                ImportedLocalModel(id="local/mine", path="/a/mine.gguf", size=77),
                ImportedLocalModel(id="local/gone", path="/a/gone.gguf", exists=False),
                ImportedLocalModel(id="local/old", path="/a/old.gguf", exists=False),
            ]
        )
        overview = await self._use_case({}, router=router, imports=imports).execute(
            refresh=True
        )
        assert overview.connected is True
        assert overview.reachable is True
        assert overview.mode == LocalRuntimeMode.BUILT_IN
        assert overview.source == LocalRuntimeSource.BUILT_IN
        assert overview.server_url is None
        assert overview.models_folder == "/models/local"
        assert imports.synced == 1
        assert router.list_calls == [True]

        by_id = {m.id: m for m in overview.models}
        assert [m.name for m in overview.models] == [
            "gone",
            "Laya",
            "mine",
            "old",
            "org/new-GGUF:Q4_K_M",
            "server-model",
        ]
        laya = by_id[CATALOG_ID]
        assert laya.source == LocalModelSource.CATALOG
        assert laya.size == 1000
        assert laya.decisions is True
        assert laya.deletable is True
        hf = by_id["org/new-GGUF:Q4_K_M"]
        assert hf.source == LocalModelSource.HUGGING_FACE
        assert hf.downloaded == 5
        assert hf.deletable is True
        mine = by_id["local/mine"]
        assert mine.source == LocalModelSource.IMPORTED
        assert mine.size == 77
        assert mine.path == "/a/mine.gguf"
        assert mine.deletable is True
        assert by_id["local/gone"].state == LocalModelState.MISSING
        old = by_id["local/old"]
        assert old.state == LocalModelState.MISSING
        assert old.source == LocalModelSource.IMPORTED
        assert old.deletable is True
        server = by_id["server-model"]
        assert server.source == LocalModelSource.SERVER
        assert server.deletable is False

    @pytest.mark.asyncio
    async def test_external_server(self):
        router = FakeRouter([_model("local/mine"), _model(CATALOG_ID, removable=False)])
        imports = FakeImports([ImportedLocalModel(id="local/mine", path="/a.gguf")])
        overview = await self._use_case(
            {"server_url": "http://server:8080"},
            runtime=FakeRuntime(EXTERNAL),
            router=router,
            imports=imports,
        ).execute()
        assert overview.mode == LocalRuntimeMode.EXTERNAL
        assert overview.server_url == "http://server:8080"
        assert overview.models_folder is None
        assert imports.synced == 0
        by_id = {m.id: m for m in overview.models}
        assert by_id["local/mine"].source == LocalModelSource.SERVER
        assert by_id["local/mine"].deletable is False
        assert by_id[CATALOG_ID].deletable is False

    @pytest.mark.asyncio
    async def test_unreachable(self):
        overview = await self._use_case(
            {},
            router=FakeRouter(error=LocalModelError(LocalModelErrorCode.UNREACHABLE)),
        ).execute()
        assert overview.connected is True
        assert overview.reachable is False
        assert overview.error == LocalModelErrorCode.UNREACHABLE
        assert overview.mode == LocalRuntimeMode.BUILT_IN

    @pytest.mark.asyncio
    async def test_runtime_failure(self):
        overview = await self._use_case(
            {},
            runtime=FakeRuntime(
                error=LocalModelError(LocalModelErrorCode.RUNTIME_FAILED)
            ),
        ).execute()
        assert overview.error == LocalModelErrorCode.RUNTIME_FAILED
        assert overview.mode is None


class TestDownloadLocalModel:
    def _use_case(self, payload=None, runtime=None, router=None, quants=None):
        hugging_face = AsyncMock()
        hugging_face.list_quants.return_value = quants or HuggingFaceQuants(
            repo="org/model-GGUF",
            quants=[HuggingFaceQuantOption(quant="Q4_K_M", file="m.gguf", size=500)],
        )
        self.hugging_face = hugging_face
        return DownloadLocalModelImpl(
            _integrations(payload),
            runtime or FakeRuntime(),
            router or FakeRouter(),
            FakeCatalog(),
            hugging_face,
        )

    @pytest.mark.asyncio
    async def test_requires_integration(self):
        with pytest.raises(ExternalIntegrationRequired):
            await self._use_case(None).execute(
                DownloadLocalModelRequest(catalog_id=CATALOG_ID)
            )

    @pytest.mark.asyncio
    async def test_downloads_catalog_entry(self):
        router = FakeRouter()
        await self._use_case({}, FakeRuntime(free=10**12), router).execute(
            DownloadLocalModelRequest(catalog_id=CATALOG_ID.lower())
        )
        assert router.downloads == [CATALOG_ID]
        self.hugging_face.list_quants.assert_not_called()

    @pytest.mark.asyncio
    async def test_unknown_catalog_entry(self):
        with pytest.raises(LocalModelError) as error:
            await self._use_case({}).execute(
                DownloadLocalModelRequest(catalog_id="unknown/repo:Q4")
            )
        assert error.value.code == LocalModelErrorCode.MODEL_NOT_FOUND

    @pytest.mark.asyncio
    async def test_downloads_hugging_face_quant(self):
        router = FakeRouter()
        await self._use_case({}, FakeRuntime(free=10**12), router).execute(
            DownloadLocalModelRequest(repo="org/model-GGUF", quant="q4_k_m")
        )
        assert router.downloads == ["org/model-GGUF:q4_k_m"]
        self.hugging_face.list_quants.assert_awaited_once_with("org/model-GGUF")

    @pytest.mark.asyncio
    async def test_rejects_encoder_models(self):
        router = FakeRouter()
        quants = HuggingFaceQuants(
            repo="org/model-GGUF",
            quants=[HuggingFaceQuantOption(quant="Q8_0", file="m.gguf", size=500)],
            kind=HuggingFaceModelKind.ENCODER,
        )
        with pytest.raises(LocalModelError) as error:
            await self._use_case(
                {}, FakeRuntime(free=10**12), router, quants=quants
            ).execute(DownloadLocalModelRequest(repo="org/model-GGUF", quant="Q8_0"))
        assert error.value.code == LocalModelErrorCode.UNSUPPORTED_MODEL
        assert router.downloads == []

    @pytest.mark.asyncio
    async def test_invalid_repo(self):
        with pytest.raises(LocalModelError) as error:
            await self._use_case({}).execute(
                DownloadLocalModelRequest(repo="../x", quant="Q4_K_M")
            )
        assert error.value.code == LocalModelErrorCode.INVALID_MODEL

    @pytest.mark.asyncio
    async def test_unknown_quant(self):
        router = FakeRouter()
        with pytest.raises(LocalModelError) as error:
            await self._use_case({}, router=router).execute(
                DownloadLocalModelRequest(repo="org/model-GGUF", quant="Q8_0")
            )
        assert error.value.code == LocalModelErrorCode.INVALID_MODEL
        assert router.downloads == []

    @pytest.mark.asyncio
    async def test_existing_model_is_noop(self):
        router = FakeRouter([_model(CATALOG_ID.upper())])
        await self._use_case({}, router=router).execute(
            DownloadLocalModelRequest(catalog_id=CATALOG_ID)
        )
        assert router.downloads == []

    @pytest.mark.asyncio
    async def test_insufficient_space(self):
        router = FakeRouter()
        with pytest.raises(LocalModelError) as error:
            await self._use_case(
                {}, FakeRuntime(free=ENTRY.size + FREE_SPACE_MARGIN - 1), router
            ).execute(DownloadLocalModelRequest(catalog_id=CATALOG_ID))
        assert error.value.code == LocalModelErrorCode.INSUFFICIENT_SPACE
        assert router.downloads == []

    @pytest.mark.asyncio
    async def test_external_server_skips_space_check(self):
        router = FakeRouter()
        await self._use_case({}, FakeRuntime(EXTERNAL, free=0), router).execute(
            DownloadLocalModelRequest(catalog_id=CATALOG_ID)
        )
        assert router.downloads == [CATALOG_ID]


class TestDeleteLocalModel:
    def _use_case(self, payload=None, runtime=None, router=None, imports=None):
        return DeleteLocalModelImpl(
            _integrations(payload),
            runtime or FakeRuntime(),
            router or FakeRouter(),
            imports or FakeImports(),
        )

    @pytest.mark.asyncio
    async def test_requires_integration(self):
        with pytest.raises(ExternalIntegrationRequired):
            await self._use_case(None).execute(LocalModelRequest(model_id="a:Q4"))

    @pytest.mark.asyncio
    async def test_deletes_cached_model(self):
        router = FakeRouter([_model("org/a-GGUF:Q4_K_M")])
        await self._use_case({}, router=router).execute(
            LocalModelRequest(model_id="org/a-GGUF:Q4_K_M")
        )
        assert router.deleted == ["org/a-GGUF:Q4_K_M"]

    @pytest.mark.asyncio
    async def test_router_removable_flag_wins(self):
        router = FakeRouter([_model("custom-name", removable=True)])
        await self._use_case({}, router=router).execute(
            LocalModelRequest(model_id="custom-name")
        )
        assert router.deleted == ["custom-name"]

    @pytest.mark.parametrize(
        "model",
        [_model("org/a-GGUF:Q4_K_M", removable=False), _model("server-model")],
    )
    @pytest.mark.asyncio
    async def test_not_deletable(self, model):
        router = FakeRouter([model])
        with pytest.raises(LocalModelError) as error:
            await self._use_case({}, router=router).execute(
                LocalModelRequest(model_id=model.id)
            )
        assert error.value.code == LocalModelErrorCode.NOT_DELETABLE
        assert router.deleted == []

    @pytest.mark.asyncio
    async def test_missing_model(self):
        with pytest.raises(LocalModelError) as error:
            await self._use_case({}).execute(LocalModelRequest(model_id="a:Q4"))
        assert error.value.code == LocalModelErrorCode.MODEL_NOT_FOUND

    @pytest.mark.asyncio
    async def test_removes_imported_model(self):
        router = FakeRouter([_model("local/mine", LocalModelState.LOADED)])
        imports = FakeImports()
        await self._use_case({}, router=router, imports=imports).execute(
            LocalModelRequest(model_id="local/mine")
        )
        assert router.unloaded == ["local/mine"]
        assert imports.removed == ["local/mine"]
        assert router.list_calls == [False, True]
        assert router.deleted == []

    @pytest.mark.asyncio
    async def test_removes_missing_imported_model(self):
        router = FakeRouter([])
        imports = FakeImports()
        await self._use_case({}, router=router, imports=imports).execute(
            LocalModelRequest(model_id="local/gone")
        )
        assert router.unloaded == []
        assert imports.removed == ["local/gone"]

    @pytest.mark.asyncio
    async def test_unknown_imported_model(self):
        with pytest.raises(LocalModelError) as error:
            await self._use_case({}, imports=FakeImports(removable=False)).execute(
                LocalModelRequest(model_id="local/unknown")
            )
        assert error.value.code == LocalModelErrorCode.MODEL_NOT_FOUND

    @pytest.mark.asyncio
    async def test_external_imported_ids_are_router_models(self):
        router = FakeRouter([_model("local/remote")])
        imports = FakeImports()
        with pytest.raises(LocalModelError) as error:
            await self._use_case(
                {}, runtime=FakeRuntime(EXTERNAL), router=router, imports=imports
            ).execute(LocalModelRequest(model_id="local/remote"))
        assert error.value.code == LocalModelErrorCode.NOT_DELETABLE
        assert imports.removed == []


class TestImportLocalModel:
    def _use_case(self, payload=None, runtime=None, router=None, imports=None):
        return ImportLocalModelImpl(
            _integrations(payload),
            runtime or FakeRuntime(),
            router or FakeRouter(),
            imports or FakeImports(),
        )

    @pytest.mark.asyncio
    async def test_requires_integration(self):
        with pytest.raises(ExternalIntegrationRequired):
            await self._use_case(None).execute(ImportLocalModelRequest(path="/a.gguf"))

    @pytest.mark.asyncio
    async def test_imports_and_reloads(self):
        router = FakeRouter()
        imports = FakeImports()
        result = await self._use_case({}, router=router, imports=imports).execute(
            ImportLocalModelRequest(path="/a.gguf")
        )
        assert result.id == "local/model"
        assert imports.added == ["/a.gguf"]
        assert router.list_calls == [True]

    @pytest.mark.asyncio
    async def test_external_server_is_unsupported(self):
        imports = FakeImports()
        with pytest.raises(LocalModelError) as error:
            await self._use_case(
                {"server_url": "http://server"},
                runtime=FakeRuntime(EXTERNAL),
                imports=imports,
            ).execute(ImportLocalModelRequest(path="/a.gguf"))
        assert error.value.code == LocalModelErrorCode.IMPORT_UNSUPPORTED
        assert imports.added == []


class TestListHuggingFaceQuants:
    @pytest.mark.asyncio
    async def test_delegates(self):
        quants = HuggingFaceQuants(repo="org/model", quants=[])
        catalog = AsyncMock()
        catalog.list_quants.return_value = quants
        assert await ListHuggingFaceQuantsImpl(catalog).execute("org/model") == quants


class TestGetExternalLabelingModels:
    def _provider(self, dynamic=True):
        provider = MagicMock()
        provider.dynamic_models.return_value = dynamic
        provider.list_models = AsyncMock(
            return_value=[ExternalLabelingModel(id="a:Q4", name="A", loaded=True)]
        )
        return provider

    @pytest.mark.asyncio
    async def test_lists_dynamic_models(self):
        provider = self._provider()
        result = await GetExternalLabelingModelsImpl(
            _integrations({}), {ExternalIntegrationId.LOCAL_MODELS: provider}
        ).execute("LOCAL_MODELS")
        assert [m.id for m in result.models] == ["a:Q4"]
        provider.list_models.assert_awaited_once_with({})

    @pytest.mark.asyncio
    async def test_static_provider_returns_empty(self):
        provider = self._provider(dynamic=False)
        result = await GetExternalLabelingModelsImpl(
            _integrations({"api_key": "x"}), {ExternalIntegrationId.OPENAI: provider}
        ).execute("OPENAI")
        assert result.models == []
        provider.list_models.assert_not_called()

    @pytest.mark.parametrize("provider_id", ["NOPE", "OPENAI"])
    @pytest.mark.asyncio
    async def test_unknown_provider(self, provider_id):
        with pytest.raises(IntegrationNotFound):
            await GetExternalLabelingModelsImpl(
                _integrations({}),
                {ExternalIntegrationId.LOCAL_MODELS: self._provider()},
            ).execute(provider_id)

    @pytest.mark.asyncio
    async def test_requires_connection(self):
        with pytest.raises(ExternalIntegrationRequired):
            await GetExternalLabelingModelsImpl(
                _integrations(None),
                {ExternalIntegrationId.LOCAL_MODELS: self._provider()},
            ).execute("LOCAL_MODELS")
