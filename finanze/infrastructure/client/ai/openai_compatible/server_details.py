import asyncio
from typing import Awaitable, Callable, Optional

from domain.ai import AIServerKind, AIServerModel

Fetch = Callable[[str], Awaitable[Optional[dict]]]

OWNER_KINDS = {
    "library": AIServerKind.OLLAMA,
    "organization_owner": AIServerKind.LM_STUDIO,
    "llamacpp": AIServerKind.LLAMA_CPP,
    "vllm": AIServerKind.VLLM,
}
LOADED_STATE = "loaded"
MAX_VERSION_LENGTH = 64


def _dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def _dicts(value) -> list[dict]:
    return (
        [item for item in value if isinstance(item, dict)]
        if isinstance(value, list)
        else []
    )


def _int(value) -> Optional[int]:
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _text(value) -> Optional[str]:
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()[:MAX_VERSION_LENGTH]


def detect_server_kind(entries: list[dict]) -> Optional[AIServerKind]:
    for entry in entries:
        kind = OWNER_KINDS.get(entry.get("owned_by"))
        if kind is not None:
            return kind
        if isinstance(entry.get("status"), dict) or isinstance(entry.get("meta"), dict):
            return AIServerKind.LLAMA_CPP
    return None


def parse_server_model(entry: dict, decisions: bool) -> AIServerModel:
    meta = _dict(entry.get("meta"))
    state = _dict(entry.get("status")).get("value")
    return AIServerModel(
        id=str(entry["id"]),
        decisions=decisions,
        loaded=state == LOADED_STATE if state else None,
        size=_int(meta.get("size")),
        context_length=_int(entry.get("max_model_len"))
        or _int(entry.get("context_length"))
        or _int(meta.get("n_ctx_train")),
    )


async def describe_server(
    kind: Optional[AIServerKind], models: list[AIServerModel], fetch: Fetch
) -> tuple[Optional[AIServerKind], Optional[str]]:
    if kind is None:
        version = _text(_dict(await fetch("/api/version")).get("version"))
        if version is None:
            return None, None
        _apply_ollama_running(models, await fetch("/api/ps"))
        return AIServerKind.OLLAMA, version
    return kind, await DESCRIBERS[kind](models, fetch)


async def _ollama(models: list[AIServerModel], fetch: Fetch) -> Optional[str]:
    version, running = await asyncio.gather(fetch("/api/version"), fetch("/api/ps"))
    _apply_ollama_running(models, running)
    return _text(_dict(version).get("version"))


def _apply_ollama_running(models: list[AIServerModel], body: Optional[dict]):
    if body is None:
        return
    running = {}
    for entry in _dicts(body.get("models")):
        for key in (entry.get("name"), entry.get("model")):
            if key:
                running[key] = entry
    for model in models:
        entry = running.get(model.id)
        model.loaded = entry is not None
        if entry is not None:
            model.size = _int(entry.get("size")) or model.size
            model.context_length = (
                _int(entry.get("context_length")) or model.context_length
            )


async def _lm_studio(models: list[AIServerModel], fetch: Fetch) -> Optional[str]:
    body = await fetch("/api/v1/models")
    entries = {entry.get("key"): entry for entry in _dicts(_dict(body).get("models"))}
    for model in models:
        entry = entries.get(model.id)
        if entry is None:
            continue
        instances = _dicts(entry.get("loaded_instances"))
        model.loaded = bool(instances)
        model.size = _int(entry.get("size_bytes")) or model.size
        loaded_context = (
            _int(_dict(instances[0].get("config")).get("context_length"))
            if instances
            else None
        )
        model.context_length = (
            loaded_context
            or _int(entry.get("max_context_length"))
            or model.context_length
        )
    return None


async def _llama_cpp(models: list[AIServerModel], fetch: Fetch) -> Optional[str]:
    props = _dict(await fetch("/props"))
    if all(model.loaded is None for model in models):
        context = _int(_dict(props.get("default_generation_settings")).get("n_ctx"))
        for model in models:
            model.loaded = True
            model.context_length = context or model.context_length
    return _text(props.get("build_info"))


async def _vllm(models: list[AIServerModel], fetch: Fetch) -> Optional[str]:
    for model in models:
        model.loaded = True
    return _text(_dict(await fetch("/version")).get("version"))


DESCRIBERS: dict[
    AIServerKind,
    Callable[[list[AIServerModel], Fetch], Awaitable[Optional[str]]],
] = {
    AIServerKind.OLLAMA: _ollama,
    AIServerKind.LM_STUDIO: _lm_studio,
    AIServerKind.LLAMA_CPP: _llama_cpp,
    AIServerKind.VLLM: _vllm,
}
