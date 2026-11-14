import asyncio
import logging
import time
from typing import Optional

from application.ports.local_model_router import LocalModelRouter
from domain.exception.exceptions import LocalModelError, LocalModelErrorCode
from domain.local_model import (
    LocalModelState,
    LocalRouterConnection,
    LocalRouterModel,
)
from infrastructure.client.ai.server_url import TRANSPORT_ERRORS
from infrastructure.client.http.http_response import HttpResponse
from infrastructure.client.http.http_session import get_http_session
from infrastructure.local_models.llama_download_progress import LlamaDownloadProgress

DECISIONS_OUTPUT = "decisions"
IMAGE_INPUT = "image"
MMPROJ_SIDECAR = "mmproj"
ROUTER_STATES = {
    "unloaded": LocalModelState.UNLOADED,
    "downloaded": LocalModelState.UNLOADED,
    "loading": LocalModelState.LOADING,
    "loaded": LocalModelState.LOADED,
    "sleeping": LocalModelState.SLEEPING,
    "downloading": LocalModelState.DOWNLOADING,
    "incomplete": LocalModelState.INCOMPLETE,
}
RUNNING_STATES = {
    LocalModelState.LOADING,
    LocalModelState.LOADED,
    LocalModelState.SLEEPING,
    LocalModelState.DOWNLOADING,
}


def _int(value) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _strings(value) -> list[str]:
    return [v for v in value if isinstance(v, str)] if isinstance(value, list) else []


def parse_router_model(entry: dict) -> Optional[LocalRouterModel]:
    model_id = entry.get("id")
    if not model_id:
        return None
    status = entry.get("status") if isinstance(entry.get("status"), dict) else {}
    state = (
        LocalModelState.FAILED
        if status.get("failed")
        else ROUTER_STATES.get(status.get("value"), LocalModelState.UNLOADED)
    )
    meta = entry.get("meta") if isinstance(entry.get("meta"), dict) else {}
    architecture = (
        entry.get("architecture") if isinstance(entry.get("architecture"), dict) else {}
    )
    modalities = _strings(architecture.get("output_modalities"))
    removable = entry.get("can_remove")
    return LocalRouterModel(
        id=str(model_id),
        state=state,
        size=_int(meta.get("size")),
        decisions=DECISIONS_OUTPUT in modalities,
        removable=removable if isinstance(removable, bool) else None,
        vision=IMAGE_INPUT in _strings(architecture.get("input_modalities")),
        has_mmproj=MMPROJ_SIDECAR in _strings(entry.get("sidecars")),
    )


class LlamaRouterClient(LocalModelRouter):
    TIMEOUT_SECONDS = 15.0
    DOWNLOAD_TIMEOUT_SECONDS = 120.0
    UNLOAD_TIMEOUT_SECONDS = 30.0
    UNLOAD_POLL_SECONDS = 0.5

    def __init__(self, progress: Optional[LlamaDownloadProgress] = None):
        self._session = get_http_session()
        self._progress = progress or LlamaDownloadProgress()
        self._log = logging.getLogger(__name__)

    async def probe(self, connection: LocalRouterConnection):
        health = await self._call(connection, "GET", "/health")
        if health.status == 404:
            raise LocalModelError(LocalModelErrorCode.NOT_A_MODEL_ROUTER)
        if health.status not in (200, 503):
            raise LocalModelError(
                LocalModelErrorCode.UNREACHABLE,
                f"Health check failed ({health.status})",
            )

        response = await self._call(connection, "GET", "/models")
        if response.status in (401, 403):
            raise LocalModelError(LocalModelErrorCode.UNAUTHORIZED)
        if not response.ok:
            raise LocalModelError(LocalModelErrorCode.NOT_A_MODEL_ROUTER)
        try:
            body = await response.json()
        except ValueError:
            raise LocalModelError(LocalModelErrorCode.NOT_A_MODEL_ROUTER)
        data = body.get("data") if isinstance(body, dict) else None
        if not isinstance(data, list):
            raise LocalModelError(LocalModelErrorCode.NOT_A_MODEL_ROUTER)
        if any(
            not isinstance(entry, dict) or not isinstance(entry.get("status"), dict)
            for entry in data
        ):
            raise LocalModelError(LocalModelErrorCode.NOT_A_MODEL_ROUTER)

    async def is_healthy(self, connection: LocalRouterConnection) -> bool:
        try:
            response = await self._call(connection, "GET", "/health")
        except LocalModelError:
            return False
        return response.ok

    async def list_models(
        self, connection: LocalRouterConnection, reload: bool = False
    ) -> list[LocalRouterModel]:
        models = await self._router_models(connection, reload)
        downloading = {m.id for m in models if m.state == LocalModelState.DOWNLOADING}
        self._progress.watch(connection, downloading)
        for model in models:
            progress = self._progress.get(model.id) if model.id in downloading else None
            if progress is not None:
                model.downloaded, total = progress
                model.size = total or model.size
        return models

    async def _router_models(
        self, connection: LocalRouterConnection, reload: bool = False
    ) -> list[LocalRouterModel]:
        params = {"reload": "1"} if reload else None
        body = await self._json(connection, "GET", "/models", params=params)
        models = []
        for entry in body.get("data") or []:
            if not isinstance(entry, dict):
                continue
            model = parse_router_model(entry)
            if model is not None:
                models.append(model)
        return models

    async def download(
        self, connection: LocalRouterConnection, model_id: str, vision: bool = False
    ):
        response = await self._call(
            connection,
            "POST",
            "/models",
            json={"model": model_id, "sidecars": [MMPROJ_SIDECAR] if vision else []},
            timeout=self.DOWNLOAD_TIMEOUT_SECONDS,
        )
        if response.status == 400:
            raise LocalModelError(
                LocalModelErrorCode.DOWNLOAD_FAILED,
                await self._error_message(response),
            )
        await self._check(response)

    async def delete(self, connection: LocalRouterConnection, model_id: str):
        await self._delete(connection, {"model": model_id})

    async def delete_vision(self, connection: LocalRouterConnection, model_id: str):
        await self._delete(connection, {"model": model_id, "sidecar": MMPROJ_SIDECAR})

    async def _delete(self, connection: LocalRouterConnection, params: dict):
        response = await self._call(connection, "DELETE", "/models", params=params)
        if response.status == 400:
            raise LocalModelError(
                LocalModelErrorCode.NOT_DELETABLE,
                await self._error_message(response),
            )
        await self._check(response)

    async def load(self, connection: LocalRouterConnection, model_id: str):
        await self._json(connection, "POST", "/models/load", json={"model": model_id})

    # The router stops a loaded instance in the background, wait until it is gone
    async def unload(self, connection: LocalRouterConnection, model_id: str):
        await self._json(connection, "POST", "/models/unload", json={"model": model_id})
        deadline = time.monotonic() + self.UNLOAD_TIMEOUT_SECONDS
        while True:
            model = next(
                (m for m in await self._router_models(connection) if m.id == model_id),
                None,
            )
            if model is None or model.state not in RUNNING_STATES:
                return
            if time.monotonic() >= deadline:
                raise LocalModelError(
                    LocalModelErrorCode.SERVER_ERROR, f"{model_id} did not unload"
                )
            await asyncio.sleep(self.UNLOAD_POLL_SECONDS)

    @staticmethod
    def _headers(connection: LocalRouterConnection) -> dict:
        if not connection.api_key:
            return {}
        return {"Authorization": f"Bearer {connection.api_key}"}

    async def _call(
        self, connection: LocalRouterConnection, method: str, path: str, **kwargs
    ) -> HttpResponse:
        kwargs.setdefault("timeout", self.TIMEOUT_SECONDS)
        try:
            return await self._session.request(
                method,
                f"{connection.base_url}{path}",
                headers=self._headers(connection),
                **kwargs,
            )
        except TRANSPORT_ERRORS as e:
            raise LocalModelError(
                LocalModelErrorCode.UNREACHABLE,
                f"llama.cpp server unreachable ({type(e).__name__})",
            ) from e

    async def _json(
        self, connection: LocalRouterConnection, method: str, path: str, **kwargs
    ) -> dict:
        response = await self._call(connection, method, path, **kwargs)
        await self._check(response)
        try:
            body = await response.json()
        except ValueError:
            raise LocalModelError(
                LocalModelErrorCode.SERVER_ERROR, "Invalid llama.cpp server response"
            )
        return body if isinstance(body, dict) else {}

    async def _check(self, response: HttpResponse):
        if response.ok:
            return
        message = await self._error_message(response)
        self._log.warning(
            f"llama.cpp server request failed with status {response.status}: {message}"
        )
        if response.status in (401, 403):
            raise LocalModelError(LocalModelErrorCode.UNAUTHORIZED, message)
        if response.status == 404:
            raise LocalModelError(LocalModelErrorCode.MODEL_NOT_FOUND, message)
        raise LocalModelError(LocalModelErrorCode.SERVER_ERROR, message)

    @staticmethod
    async def _error_message(response: HttpResponse) -> Optional[str]:
        try:
            body = await response.json()
        except Exception:
            return None
        error = body.get("error") if isinstance(body, dict) else None
        if isinstance(error, dict):
            return error.get("message")
        return None
