import sqlite3
from pathlib import Path
from unittest.mock import AsyncMock
from urllib.parse import urlsplit

import httpx
import pytest
import pytest_asyncio

from application.use_cases.connect_external_integration import (
    ConnectExternalIntegrationImpl,
)
from application.use_cases.delete_local_model import DeleteLocalModelImpl
from application.use_cases.disconnect_external_integration import (
    DisconnectExternalIntegrationImpl,
)
from application.use_cases.download_local_model import DownloadLocalModelImpl
from application.use_cases.get_external_integrations import (
    GetExternalIntegrationsImpl,
)
from application.use_cases.get_external_labeling_models import (
    GetExternalLabelingModelsImpl,
)
from application.use_cases.get_external_labeling_providers import (
    GetExternalLabelingProvidersImpl,
)
from application.use_cases.get_local_models import GetLocalModelsImpl
from application.use_cases.import_local_model import ImportLocalModelImpl
from application.use_cases.list_hugging_face_quants import ListHuggingFaceQuantsImpl
from domain.data_init import DatasourceInitContext
from domain.external_integration import ExternalIntegrationId
from infrastructure.client.http.http_response import HttpResponse
from infrastructure.controller.config import quart
from infrastructure.controller.exception_handler import register_exception_handlers
from infrastructure.controller.routes.connect_external_integration import (
    connect_external_integration,
)
from infrastructure.controller.routes.delete_local_model import delete_local_model
from infrastructure.controller.routes.disconnect_external_integration import (
    disconnect_external_integration,
)
from infrastructure.controller.routes.download_local_model import (
    download_local_model,
)
from infrastructure.controller.routes.get_external_integrations import (
    get_external_integrations,
)
from infrastructure.controller.routes.get_external_labeling_models import (
    get_external_labeling_models,
)
from infrastructure.controller.routes.get_external_labeling_providers import (
    get_external_labeling_providers,
)
from infrastructure.controller.routes.get_local_models import get_local_models
from infrastructure.controller.routes.import_local_model import import_local_model
from infrastructure.controller.routes.list_hugging_face_quants import (
    list_hugging_face_quants,
)
from infrastructure.labeling.ai_labeling_presets import (
    LABELING_BATCH_SIZES,
    LABELING_PRESETS,
)
from infrastructure.labeling.ai_labeling_provider import AILabelingProvider
from infrastructure.local_models import llama_router_process
from infrastructure.local_models.huggingface_catalog_client import (
    HuggingFaceCatalogClient,
)
from infrastructure.local_models.llama_router_client import LlamaRouterClient
from infrastructure.local_models.llama_router_process import (
    PID_FILE,
    LlamaRouterProcess,
)
from infrastructure.local_models.local_model_catalog import StaticLocalModelCatalog
from infrastructure.local_models.local_model_imports import (
    LocalModelFileImports,
    presets_path,
)
from infrastructure.local_models.local_model_runtime import LocalModelRuntimeAdapter
from infrastructure.local_models.local_models_ai_client import LocalModelsAIClient
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.db.upgrader import DatabaseUpgrader
from infrastructure.repository.db.version_registry import versions
from infrastructure.repository.external_integration.external_integration_repository import (
    ExternalIntegrationRepository,
)

LOCAL_MODELS = ExternalIntegrationId.LOCAL_MODELS
HF_REPO = "org/tiny-GGUF"
HF_MODEL = f"{HF_REPO}:Q4_K_M"
NOT_A_ROUTER_HOST = "not-a-router"


def _response(status: int, body=None) -> HttpResponse:
    return HttpResponse(httpx.Response(status, json=body if body is not None else {}))


class FakeLlamaServer:
    def __init__(self, models_dir: Path):
        self.models_dir = models_dir
        self.api_key = None
        self.cached: dict[str, dict] = {}
        self.presets: dict[str, str] = {}
        self.states: dict[str, str] = {}
        self.hf_info = {
            "id": HF_REPO,
            "siblings": [
                {"rfilename": "tiny-Q4_K_M.gguf", "lfs": {"size": 1000}},
                {"rfilename": "tiny-Q8_0.gguf", "size": 10**18},
                {"rfilename": "README.md", "size": 10},
            ],
            "gguf": {"architecture": "llama", "total": 1000},
        }

    def _authorized(self, headers) -> bool:
        if self.api_key is None:
            return True
        return (headers or {}).get("Authorization") == f"Bearer {self.api_key}"

    def _reload_presets(self):
        self.presets = {}
        current = None
        for line in presets_path(self.models_dir).read_text().splitlines():
            if line.startswith("[") and line.endswith("]"):
                current = line[1:-1]
            elif current and line.startswith("model = "):
                self.presets[current] = line[len("model = ") :]

    def _entries(self) -> list[dict]:
        entries = [
            {
                "id": model_id,
                "status": {"value": self.states.get(model_id, "downloaded")},
                "meta": {"size": size},
                "can_remove": True,
            }
            for model_id, size in self.cached.items()
        ]
        entries += [
            {
                "id": model_id,
                "status": {"value": self.states.get(model_id, "unloaded")},
                "can_remove": False,
            }
            for model_id in self.presets
        ]
        return entries

    async def request(self, method, url, headers=None, params=None, json=None, **_):
        split = urlsplit(url)
        if split.hostname == NOT_A_ROUTER_HOST:
            return _response(404)
        path = split.path
        if path == "/health":
            return _response(200, {"status": "ok"})
        if not self._authorized(headers):
            return _response(401, {"error": {"message": "Unauthorized"}})
        if path == "/models" and method == "GET":
            if params and params.get("reload"):
                self._reload_presets()
            return _response(200, {"data": self._entries()})
        if path == "/models" and method == "POST":
            self.cached[json["model"]] = 1000
            return _response(200, {"success": True})
        if path == "/models" and method == "DELETE":
            if params["model"] not in self.cached:
                return _response(404, {"error": {"message": "Not found"}})
            del self.cached[params["model"]]
            return _response(200, {"success": True})
        if path in ("/models/load", "/models/unload"):
            loaded = path.endswith("/load")
            self.states[json["model"]] = "loaded" if loaded else "unloaded"
            return _response(200, {"success": True})
        return _response(404)

    async def get(self, url, params=None, **_):
        if not url.endswith(f"/api/models/{HF_REPO}"):
            return _response(404)
        return _response(200, self.hf_info)


class FakeProcess:
    def __init__(self, pid: int):
        self.pid = pid
        self.returncode = None

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        self.returncode = 0
        return 0


class Ctx:
    def __init__(self, http, server, spawned, models_dir, runtime, tmp_path):
        self.http = http
        self.server = server
        self.spawned = spawned
        self.models_dir = models_dir
        self.runtime = runtime
        self.tmp_path = tmp_path

    async def connect(self, payload=None):
        return await self.http.post(
            f"/api/v1/integrations/{LOCAL_MODELS.value}",
            json={"payload": payload if payload is not None else {}},
        )

    async def overview(self, refresh=False):
        response = await self.http.get(
            "/api/v1/ai/local/models", query_string={"refresh": "1"} if refresh else {}
        )
        assert response.status_code == 200
        return await response.get_json()

    def gguf(self, name: str) -> Path:
        path = self.tmp_path / "downloads" / name
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(b"GGUF" + b"\0" * 16)
        return path


@pytest.fixture
def executable(tmp_path) -> Path:
    path = tmp_path / "bin" / "finanze-llama-server"
    path.parent.mkdir()
    path.write_text("#!/bin/sh\n")
    path.chmod(0o755)
    return path


@pytest_asyncio.fixture
async def ctx(tmp_path, executable, monkeypatch):
    monkeypatch.setattr(
        llama_router_process, "_kill_tree", lambda pid, force=False: None
    )

    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    client = DBClient(connection)
    await DatabaseUpgrader(
        client, versions, DatasourceInitContext(config=AsyncMock())
    ).upgrade()
    integrations = ExternalIntegrationRepository(client)

    models_dir = tmp_path / "models"
    server = FakeLlamaServer(models_dir)
    spawned: list[FakeProcess] = []

    def spawn(args, env, log_path):
        server.api_key = env["LLAMA_API_KEY"]
        process = FakeProcess(5000 + len(spawned))
        spawned.append(process)
        return process

    router = LlamaRouterClient()
    router._session = server
    process = LlamaRouterProcess(executable, models_dir, router, spawn=spawn)
    process.HEALTH_POLL_SECONDS = 0
    runtime = LocalModelRuntimeAdapter(process)
    imports = LocalModelFileImports(models_dir)
    catalog = StaticLocalModelCatalog()
    hugging_face = HuggingFaceCatalogClient()
    hugging_face._session = server
    ai_client = LocalModelsAIClient(runtime, router, catalog)
    clients = {LOCAL_MODELS: ai_client}
    providers = {
        LOCAL_MODELS: AILabelingProvider(
            ai_client,
            LABELING_PRESETS.get(LOCAL_MODELS, []),
            LABELING_BATCH_SIZES.get(LOCAL_MODELS),
        )
    }

    get_integrations_uc = GetExternalIntegrationsImpl(integrations, clients)
    connect_uc = ConnectExternalIntegrationImpl(integrations, clients)
    disconnect_uc = DisconnectExternalIntegrationImpl(integrations, clients)
    get_models_uc = GetLocalModelsImpl(integrations, runtime, router, imports, catalog)
    download_uc = DownloadLocalModelImpl(
        integrations, runtime, router, catalog, hugging_face
    )
    delete_uc = DeleteLocalModelImpl(integrations, runtime, router, imports)
    import_uc = ImportLocalModelImpl(integrations, runtime, router, imports)
    quants_uc = ListHuggingFaceQuantsImpl(hugging_face)
    providers_uc = GetExternalLabelingProvidersImpl(integrations, providers)
    labeling_models_uc = GetExternalLabelingModelsImpl(integrations, providers)

    static_dir = tmp_path / "static"
    static_dir.mkdir()
    app = quart(static_dir)
    register_exception_handlers(app)

    @app.route("/api/v1/integrations", methods=["GET"])
    async def get_integrations_route():
        return await get_external_integrations(get_integrations_uc)

    @app.route("/api/v1/integrations/<integration_id>", methods=["POST"])
    async def connect_route(integration_id: str):
        return await connect_external_integration(connect_uc, integration_id)

    @app.route("/api/v1/integrations/<integration_id>", methods=["DELETE"])
    async def disconnect_route(integration_id: str):
        return await disconnect_external_integration(disconnect_uc, integration_id)

    @app.route("/api/v1/ai/local/models", methods=["GET"])
    async def get_local_models_route():
        return await get_local_models(get_models_uc)

    @app.route("/api/v1/ai/local/models", methods=["DELETE"])
    async def delete_local_model_route():
        return await delete_local_model(delete_uc)

    @app.route("/api/v1/ai/local/models/download", methods=["POST"])
    async def download_local_model_route():
        return await download_local_model(download_uc)

    @app.route("/api/v1/ai/local/models/import", methods=["POST"])
    async def import_local_model_route():
        return await import_local_model(import_uc)

    @app.route("/api/v1/ai/local/huggingface/quants", methods=["GET"])
    async def quants_route():
        return await list_hugging_face_quants(quants_uc)

    @app.route("/api/v1/labeling/external/providers", methods=["GET"])
    async def providers_route():
        return await get_external_labeling_providers(providers_uc)

    @app.route(
        "/api/v1/labeling/external/providers/<provider_id>/models", methods=["GET"]
    )
    async def labeling_models_route(provider_id: str):
        return await get_external_labeling_models(labeling_models_uc, provider_id)

    yield Ctx(app.test_client(), server, spawned, models_dir, runtime, tmp_path)

    await runtime.stop()
    connection.close()


@pytest.mark.asyncio
async def test_integrations_are_listed_with_optional_fields(ctx):
    response = await ctx.http.get("/api/v1/integrations")
    integrations = {i["id"]: i for i in (await response.get_json())["integrations"]}

    local = integrations["LOCAL_MODELS"]
    assert local["name"] == "Local models"
    assert local["status"] == "OFF"
    assert local["available"] is True
    assert local["optional_fields"] == ["api_key", "server_url"]
    custom = integrations["OPENAI_COMPATIBLE"]
    assert custom["name"] == "Custom endpoint"
    assert custom["optional_fields"] == ["api_key"]
    assert custom["available"] is False


@pytest.mark.asyncio
async def test_not_connected_does_not_start_engine(ctx):
    overview = await ctx.overview()
    assert overview["connected"] is False
    assert overview["capabilities"]["built_in_available"] is True
    assert overview["capabilities"]["can_import_files"] is True
    assert overview["catalog"]
    assert ctx.spawned == []

    response = await ctx.http.post(
        "/api/v1/ai/local/models/download", json={"repo": HF_REPO, "quant": "Q4_K_M"}
    )
    assert response.status_code == 409
    assert (await response.get_json())["code"] == "REQUIRED_INTEGRATION"


@pytest.mark.asyncio
async def test_built_in_model_lifecycle(ctx):
    response = await ctx.connect()
    assert response.status_code == 204
    assert len(ctx.spawned) == 1
    assert (ctx.models_dir / PID_FILE).read_text() == "5000"

    overview = await ctx.overview()
    assert overview["connected"] is True
    assert overview["reachable"] is True
    assert overview["mode"] == "BUILT_IN"
    assert overview["models"] == []
    assert overview["models_folder"] == str(ctx.models_dir / "local")

    response = await ctx.http.get(
        "/api/v1/ai/local/huggingface/quants",
        query_string={"repo": f"https://huggingface.co/{HF_REPO}"},
    )
    assert response.status_code == 200
    quants = await response.get_json()
    assert quants["repo"] == HF_REPO
    assert quants["kind"] == "CHAT"
    assert [q["quant"] for q in quants["quants"]] == ["Q4_K_M", "Q8_0"]

    response = await ctx.http.post(
        "/api/v1/ai/local/models/download", json={"repo": HF_REPO, "quant": "Q4_K_M"}
    )
    assert response.status_code == 204
    assert HF_MODEL in ctx.server.cached

    model_file = ctx.gguf("Phi Mini.gguf")
    response = await ctx.http.post(
        "/api/v1/ai/local/models/import", json={"path": str(model_file)}
    )
    assert response.status_code == 200
    imported = await response.get_json()
    assert imported["id"] == "local/phi-mini"
    assert ctx.server.presets == {"local/phi-mini": str(model_file.resolve())}

    overview = await ctx.overview(refresh=True)
    models = {m["id"]: m for m in overview["models"]}
    assert models[HF_MODEL]["source"] == "HUGGING_FACE"
    assert models[HF_MODEL]["deletable"] is True
    assert models[HF_MODEL]["size"] == 1000
    assert models["local/phi-mini"]["source"] == "IMPORTED"
    assert models["local/phi-mini"]["name"] == "phi-mini"
    assert models["local/phi-mini"]["path"] == str(model_file.resolve())

    response = await ctx.http.get("/api/v1/labeling/external/providers")
    provider = next(
        p for p in (await response.get_json())["providers"] if p["id"] == "LOCAL_MODELS"
    )
    assert provider["connected"] is True
    assert provider["dynamic_models"] is True
    assert provider["custom_models"] is False

    response = await ctx.http.get(
        "/api/v1/labeling/external/providers/LOCAL_MODELS/models"
    )
    assert response.status_code == 200
    labeling_models = (await response.get_json())["models"]
    assert {m["id"] for m in labeling_models} == {HF_MODEL, "local/phi-mini"}

    ctx.server.states["local/phi-mini"] = "loaded"
    response = await ctx.http.delete(
        "/api/v1/ai/local/models", query_string={"model_id": "local/phi-mini"}
    )
    assert response.status_code == 204
    assert ctx.server.states["local/phi-mini"] == "unloaded"
    assert ctx.server.presets == {}
    assert model_file.exists()

    response = await ctx.http.delete(
        "/api/v1/ai/local/models", query_string={"model_id": HF_MODEL}
    )
    assert response.status_code == 204
    assert ctx.server.cached == {}

    response = await ctx.http.delete(f"/api/v1/integrations/{LOCAL_MODELS.value}")
    assert response.status_code == 204
    assert ctx.spawned[0].returncode == 0
    assert not (ctx.models_dir / PID_FILE).exists()
    assert (await ctx.overview())["connected"] is False


@pytest.mark.asyncio
async def test_model_in_folder_is_listed(ctx):
    await ctx.connect()
    local_dir = ctx.models_dir / "local"
    local_dir.mkdir(parents=True, exist_ok=True)
    (local_dir / "qwen.gguf").write_bytes(b"GGUF")

    overview = await ctx.overview(refresh=True)
    assert [m["id"] for m in overview["models"]] == ["local/qwen"]

    response = await ctx.http.delete(
        "/api/v1/ai/local/models", query_string={"model_id": "local/qwen"}
    )
    assert response.status_code == 204
    assert not (local_dir / "qwen.gguf").exists()
    assert (await ctx.overview(refresh=True))["models"] == []


@pytest.mark.asyncio
async def test_download_errors(ctx):
    await ctx.connect()

    for body in ({}, {"repo": HF_REPO}, {"catalog_id": 1}):
        response = await ctx.http.post("/api/v1/ai/local/models/download", json=body)
        assert response.status_code == 400

    response = await ctx.http.post(
        "/api/v1/ai/local/models/download", json={"repo": HF_REPO, "quant": "Q8_0"}
    )
    assert response.status_code == 507
    assert (await response.get_json())["code"] == "INSUFFICIENT_SPACE"

    response = await ctx.http.post(
        "/api/v1/ai/local/models/download", json={"repo": HF_REPO, "quant": "Q2_K"}
    )
    assert response.status_code == 400
    assert (await response.get_json())["code"] == "INVALID_MODEL"

    response = await ctx.http.post(
        "/api/v1/ai/local/models/download", json={"catalog_id": "unknown/repo:Q4"}
    )
    assert response.status_code == 404
    assert ctx.server.cached == {}


@pytest.mark.asyncio
async def test_encoder_models_are_unsupported(ctx):
    await ctx.connect()
    ctx.server.hf_info["gguf"] = {"architecture": "modern-bert", "causal": False}

    response = await ctx.http.get(
        "/api/v1/ai/local/huggingface/quants", query_string={"repo": HF_REPO}
    )
    assert response.status_code == 200
    assert (await response.get_json())["kind"] == "ENCODER"

    response = await ctx.http.post(
        "/api/v1/ai/local/models/download", json={"repo": HF_REPO, "quant": "Q4_K_M"}
    )
    assert response.status_code == 400
    assert (await response.get_json())["code"] == "UNSUPPORTED_MODEL"
    assert ctx.server.cached == {}


@pytest.mark.asyncio
async def test_delete_and_import_errors(ctx):
    await ctx.connect()

    response = await ctx.http.delete("/api/v1/ai/local/models")
    assert response.status_code == 400

    response = await ctx.http.delete(
        "/api/v1/ai/local/models", query_string={"model_id": HF_MODEL}
    )
    assert response.status_code == 404
    assert (await response.get_json())["code"] == "MODEL_NOT_FOUND"

    response = await ctx.http.post("/api/v1/ai/local/models/import", json={})
    assert response.status_code == 400

    not_gguf = ctx.tmp_path / "notes.gguf"
    not_gguf.write_bytes(b"text")
    response = await ctx.http.post(
        "/api/v1/ai/local/models/import", json={"path": str(not_gguf)}
    )
    assert response.status_code == 400
    assert (await response.get_json())["code"] == "INVALID_FILE"

    response = await ctx.http.get("/api/v1/ai/local/huggingface/quants")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_external_server(ctx):
    response = await ctx.connect(
        {"server_url": "http://router:8080/v1", "api_key": " "}
    )
    assert response.status_code == 204
    assert ctx.spawned == []

    overview = await ctx.overview()
    assert overview["mode"] == "EXTERNAL"
    assert overview["source"] == "PAYLOAD"
    assert overview["server_url"] == "http://router:8080"
    assert overview["models_folder"] is None

    response = await ctx.http.post(
        "/api/v1/ai/local/models/import", json={"path": str(ctx.gguf("a.gguf"))}
    )
    assert response.status_code == 409
    assert (await response.get_json())["code"] == "IMPORT_UNSUPPORTED"

    response = await ctx.http.post(
        "/api/v1/ai/local/models/download", json={"repo": HF_REPO, "quant": "Q8_0"}
    )
    assert response.status_code == 204
    assert f"{HF_REPO}:Q8_0" in ctx.server.cached


@pytest.mark.parametrize(
    "payload, status, code",
    [
        ({"server_url": "ftp://router"}, 400, "INVALID_URL"),
        ({"server_url": f"http://{NOT_A_ROUTER_HOST}:8080"}, 400, "NOT_A_MODEL_ROUTER"),
    ],
)
@pytest.mark.asyncio
async def test_connect_errors(ctx, payload, status, code):
    response = await ctx.connect(payload)
    assert response.status_code == status
    assert (await response.get_json())["code"] == code
    assert (await ctx.overview())["connected"] is False


@pytest.mark.asyncio
async def test_connect_requires_payload_object(ctx):
    response = await ctx.http.post(
        f"/api/v1/integrations/{LOCAL_MODELS.value}", json={"payload": "x"}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_external_server_unauthorized(ctx):
    ctx.server.api_key = "secret"
    response = await ctx.connect({"server_url": "http://router:8080"})
    assert response.status_code == 401
    assert (await response.get_json())["code"] == "INVALID_CREDENTIALS"

    response = await ctx.connect(
        {"server_url": "http://router:8080", "api_key": "secret"}
    )
    assert response.status_code == 204
