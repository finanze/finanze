from unittest.mock import AsyncMock

import httpx
import pytest
from domain.exception.exceptions import LocalModelError, LocalModelErrorCode
from domain.local_model import HuggingFaceModelKind
from infrastructure.client.http.http_response import HttpResponse
from infrastructure.local_models.huggingface_catalog_client import (
    MODEL_INFO_PARAMS,
    HuggingFaceCatalogClient,
    listed_tag,
    model_kind,
    normalize_repo,
    resolve_tag_file,
)


def _client(response) -> HuggingFaceCatalogClient:
    client = HuggingFaceCatalogClient()
    client._session = AsyncMock()
    if isinstance(response, Exception):
        client._session.get.side_effect = response
    else:
        client._session.get.return_value = response
    return client


def _file(path: str, size: int | None = None, lfs: bool = True) -> dict:
    entry = {"rfilename": path}
    if size is not None:
        if lfs:
            entry["lfs"] = {"size": size}
        else:
            entry["size"] = size
    return entry


def _info(*files, gguf: dict | None = None) -> dict:
    info = {"id": "org/model-GGUF", "siblings": list(files)}
    if gguf is not None:
        info["gguf"] = gguf
    return info


class TestNormalizeRepo:
    @pytest.mark.parametrize(
        "value",
        [
            "unsloth/Qwen3-1.7B-GGUF",
            " https://huggingface.co/unsloth/Qwen3-1.7B-GGUF ",
            "https://huggingface.co/unsloth/Qwen3-1.7B-GGUF/tree/main",
            "hf.co/unsloth/Qwen3-1.7B-GGUF?x=1",
            "HUGGINGFACE.CO/unsloth/Qwen3-1.7B-GGUF/",
        ],
    )
    def test_accepts_repo_and_urls(self, value):
        assert normalize_repo(value) == "unsloth/Qwen3-1.7B-GGUF"

    @pytest.mark.parametrize(
        "value", ["", "qwen", "https://example.com/a/b", "a/b c", "../etc/passwd"]
    )
    def test_rejects_invalid(self, value):
        with pytest.raises(LocalModelError) as error:
            normalize_repo(value)
        assert error.value.code == LocalModelErrorCode.INVALID_MODEL


class TestListedTag:
    @pytest.mark.parametrize(
        "file_name, quant",
        [
            ("Qwen3-1.7B-Q4_K_M.gguf", "Q4_K_M"),
            ("gemma-3-1b-it-q8_0.gguf", "Q8_0"),
            ("sub/dir/model.IQ4_XS.gguf", "IQ4_XS"),
            ("model-UD-Q4_K_XL.gguf", "Q4_K_XL"),
            ("model-Q4_K_M-imat.gguf", "IMAT"),
            ("model-BF16.gguf", "BF16"),
            ("gpt-oss-20b-MXFP4.gguf", "MXFP4"),
        ],
    )
    def test_extracts(self, file_name, quant):
        assert listed_tag(file_name) == quant

    @pytest.mark.parametrize(
        "file_name",
        [
            "README.md",
            "mmproj-model-F16.gguf",
            "mtp-model-Q8_0.gguf",
            "model-Q4_K_M-00001-of-00002.gguf",
            "model.gguf",
        ],
    )
    def test_ignores(self, file_name):
        assert listed_tag(file_name) is None


class TestResolveTagFile:
    def test_first_match_wins(self):
        paths = [
            "model-IQ4_XS-imat.gguf",
            "model-Q4_K_M-imat.gguf",
            "model-Q4_K_M.gguf",
        ]
        assert resolve_tag_file(paths, "Q4_K_M") == "model-Q4_K_M-imat.gguf"
        assert resolve_tag_file(paths, "q4_k_m") == "model-Q4_K_M-imat.gguf"
        assert resolve_tag_file(paths, "IMAT") == "model-IQ4_XS-imat.gguf"

    def test_skips_sidecars_imatrix_and_later_shards(self):
        paths = [
            "mmproj-Q8_0.gguf",
            "model-Q8_0.imatrix.gguf",
            "model-Q8_0-00002-of-00002.gguf",
            "model-Q8_0-00001-of-00002.gguf",
        ]
        assert resolve_tag_file(paths, "Q8_0") == "model-Q8_0-00001-of-00002.gguf"

    def test_no_match(self):
        assert resolve_tag_file(["model-Q8_0.gguf"], "Q4_K_M") is None


class TestModelKind:
    @pytest.mark.parametrize(
        "gguf, kind",
        [
            (
                {"architecture": "modern-bert", "decision_type": "laya"},
                HuggingFaceModelKind.DECISIONS,
            ),
            (
                {"architecture": "qwen35", "decision_type": "kev"},
                HuggingFaceModelKind.DECISIONS,
            ),
            (
                {"architecture": "modern-bert", "causal": False},
                HuggingFaceModelKind.ENCODER,
            ),
            ({"architecture": "qwen3"}, HuggingFaceModelKind.CHAT),
            ({"architecture": "llama", "causal": True}, HuggingFaceModelKind.CHAT),
            ({}, HuggingFaceModelKind.UNKNOWN),
            (None, HuggingFaceModelKind.UNKNOWN),
            ("gguf", HuggingFaceModelKind.UNKNOWN),
        ],
    )
    def test_classifies(self, gguf, kind):
        assert model_kind(gguf) == kind


class TestListQuants:
    @pytest.mark.asyncio
    async def test_lists_quants_by_size(self):
        client = _client(
            HttpResponse(
                httpx.Response(
                    200,
                    json=_info(
                        _file("README.md", 10, lfs=False),
                        _file("model-Q8_0.gguf", 800),
                        _file("model-Q4_K_M.gguf", 400),
                        _file("extra/long-name-Q4_K_M.gguf", 401),
                        _file("model-F16.gguf"),
                        _file("mmproj-F16.gguf", 50),
                        "invalid",
                        {"size": 1},
                        gguf={"architecture": "qwen3", "total": 1},
                    ),
                )
            )
        )
        result = await client.list_quants("https://huggingface.co/org/model-GGUF")
        assert result.repo == "org/model-GGUF"
        assert result.kind == HuggingFaceModelKind.CHAT
        assert [(q.quant, q.file, q.size) for q in result.quants] == [
            ("Q4_K_M", "model-Q4_K_M.gguf", 400),
            ("Q8_0", "model-Q8_0.gguf", 800),
            ("F16", "model-F16.gguf", None),
        ]
        call = client._session.get.call_args
        assert call.args[0] == "https://huggingface.co/api/models/org/model-GGUF"
        assert call.kwargs["params"] == MODEL_INFO_PARAMS

    @pytest.mark.parametrize(
        "gguf, kind",
        [
            (
                {"architecture": "modern-bert", "causal": False},
                HuggingFaceModelKind.ENCODER,
            ),
            (
                {"architecture": "modern-bert", "decision_type": "laya"},
                HuggingFaceModelKind.DECISIONS,
            ),
            (None, HuggingFaceModelKind.UNKNOWN),
        ],
    )
    @pytest.mark.asyncio
    async def test_reports_model_kind(self, gguf, kind):
        client = _client(
            HttpResponse(
                httpx.Response(200, json=_info(_file("m-Q8_0.gguf", 1), gguf=gguf))
            )
        )
        result = await client.list_quants("org/model-GGUF")
        assert result.kind == kind

    @pytest.mark.asyncio
    async def test_only_offers_quants_listed_under_the_same_tag(self):
        client = _client(
            HttpResponse(
                httpx.Response(
                    200,
                    json=_info(
                        _file("model-IQ4_XS-imat.gguf", 235),
                        _file("model-IQ4_XS.gguf", 236),
                        _file("model-Q4_K_M-imat.gguf", 249),
                        _file("model-Q4_K_M.gguf", 248),
                        _file("model-Q8_0.gguf", 341),
                        _file("model-UD-Q4_K_XL.gguf", 300),
                    ),
                )
            )
        )
        result = await client.list_quants("org/model-GGUF")
        assert [(q.quant, q.file, q.size) for q in result.quants] == [
            ("IMAT", "model-IQ4_XS-imat.gguf", 235),
            ("Q4_K_XL", "model-UD-Q4_K_XL.gguf", 300),
            ("Q8_0", "model-Q8_0.gguf", 341),
        ]

    @pytest.mark.parametrize("status", [401, 403, 404])
    @pytest.mark.asyncio
    async def test_missing_or_gated_repo(self, status):
        client = _client(HttpResponse(httpx.Response(status, json={})))
        with pytest.raises(LocalModelError) as error:
            await client.list_quants("org/model")
        assert error.value.code == LocalModelErrorCode.HUGGING_FACE_REPO_NOT_FOUND

    @pytest.mark.asyncio
    async def test_repo_without_gguf(self):
        client = _client(
            HttpResponse(httpx.Response(200, json=_info(_file("a.bin", 1))))
        )
        result = await client.list_quants("org/model")
        assert result.repo == "org/model"
        assert result.quants == []

    @pytest.mark.parametrize(
        "response",
        [
            httpx.ConnectError("offline"),
            HttpResponse(httpx.Response(500, json={})),
            HttpResponse(httpx.Response(200, text="<html>")),
            HttpResponse(httpx.Response(200, json=[])),
        ],
    )
    @pytest.mark.asyncio
    async def test_hugging_face_unavailable(self, response):
        client = _client(response)
        with pytest.raises(LocalModelError) as error:
            await client.list_quants("org/model")
        assert error.value.code == LocalModelErrorCode.HUGGING_FACE_UNAVAILABLE

    @pytest.mark.asyncio
    async def test_invalid_repo_skips_request(self):
        client = _client(HttpResponse(httpx.Response(200, json=[])))
        with pytest.raises(LocalModelError):
            await client.list_quants("not a repo")
        client._session.get.assert_not_called()
