import asyncio
import json
from datetime import datetime, timedelta

import httpx
import pytest
from dateutil.tz import tzlocal
from domain.ai import (
    AIClientFeature,
    AIGenerationRequest,
    AIGenerationStatus,
    AIJsonSchema,
    AIMessage,
    AIMessageRole,
    AIModelCapability,
    AIReasoningEffort,
)
from domain.dezimal import Dezimal
from domain.exception.exceptions import (
    AIProviderError,
    AIProviderErrorCode,
    IntegrationSetupError,
    IntegrationSetupErrorCode,
)
from domain.external_integration import (
    CompleteExternalIntegrationConnectionRequest,
    ExternalIntegrationId,
)
from infrastructure.client.ai.chatgpt.chatgpt_client import ChatGPTClient
from infrastructure.client.http.http_response import HttpResponse

CHATGPT = ExternalIntegrationId.CHATGPT
NOW = datetime(2026, 11, 3, 12, 0, tzinfo=tzlocal())
MODELS = {
    "models": [
        {
            "slug": "gpt-6-sol",
            "display_name": "GPT-6 Sol",
            "visibility": "list",
            "supported_reasoning_levels": [
                {"effort": "low", "description": "Fast"},
                {"effort": "medium", "description": "Balanced"},
                {"effort": "high", "description": "Deep"},
            ],
        },
        {"slug": "gpt-6-mini", "display_name": "GPT-6 mini", "visibility": "list"},
        {"slug": "gpt-6-internal", "display_name": "Internal", "visibility": "hide"},
    ]
}


def _payload(access: str = "access-1", refresh: str = "refresh-1", **extra) -> dict:
    return {
        "client_id": "oaiapp_issued",
        "access_token": access,
        "refresh_token": refresh,
        "expires_at": (NOW + timedelta(hours=1)).isoformat(),
        **extra,
    }


def _sse(*events: dict) -> str:
    return "".join(
        f"event: {event['type']}\ndata: {json.dumps(event)}\n\n" for event in events
    )


def _completed(text: str = '{"labels": []}', usage=None) -> str:
    response = {
        "status": "completed",
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": text}],
            }
        ],
    }
    if usage:
        response["usage"] = usage
    return _sse(
        {"type": "response.created", "response": {"status": "in_progress"}},
        {"type": "response.output_text.delta", "delta": text},
        {"type": "response.completed", "response": response},
    )


class FakePort:
    def __init__(self, payload=None):
        self.payload = payload
        self.status = "ON" if payload else "OFF"
        self.updates: list[dict] = []

    async def get_payload(self, integration, include_expired=False):
        if self.status == "ON" or (include_expired and self.status == "EXPIRED"):
            return self.payload
        return None

    async def update_payload(self, integration, payload):
        if self.status == "ON":
            self.payload = payload
            self.updates.append(payload)

    async def expire(self, integration):
        if self.status == "ON":
            self.status = "EXPIRED"


class FakeOAuth:
    def __init__(self):
        self.refresh_results: list = []
        self.refreshed: list[dict] = []
        self.revoked: list[dict] = []
        self.started: list[tuple] = []
        self.completed_payload = _payload()

    async def refresh(self, payload):
        self.refreshed.append(payload)
        await asyncio.sleep(0)
        result = self.refresh_results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    async def revoke(self, payload):
        self.revoked.append(payload)

    async def start(self, completion_url, previous):
        self.started.append((completion_url, previous))
        return "https://auth.openai.com/api/accounts/authorize?state=s"

    async def complete(self, request):
        return self.completed_payload

    def destination(self, state):
        return "finanze://integration/complete" if state == "known" else None


class FakeApi:
    def __init__(self):
        self.models = (200, MODELS)
        self.responses: list[tuple[int, object]] = []
        self.rejected_tokens: set[str] = set()
        self.calls: list[tuple[str, str, dict, dict]] = []

    async def request(self, method, url, headers=None, **kwargs):
        self.calls.append((method, url, headers or {}, kwargs))
        token = (headers or {}).get("Authorization", "").removeprefix("Bearer ")
        if token in self.rejected_tokens:
            return HttpResponse(httpx.Response(401, json={"detail": "Unauthorized"}))
        if url.endswith("/models"):
            status, body = self.models
            return HttpResponse(httpx.Response(status, json=body))
        status, body = self.responses.pop(0)
        if isinstance(body, str):
            return HttpResponse(
                httpx.Response(
                    status, text=body, headers={"content-type": "text/event-stream"}
                )
            )
        return HttpResponse(httpx.Response(status, json=body))

    def posts(self) -> list[tuple[str, str, dict, dict]]:
        return [call for call in self.calls if call[0] == "POST"]


def _client(port=None, oauth=None, api=None, now=NOW):
    client = ChatGPTClient(
        oauth or FakeOAuth(),
        port or FakePort(_payload()),
        now=lambda: now,
    )
    client.BACKOFF_SECONDS = 0
    client._session = api or FakeApi()
    return client


def _request(**kwargs) -> AIGenerationRequest:
    return AIGenerationRequest(
        **{
            "model": "gpt-6-sol",
            "messages": [
                AIMessage(role=AIMessageRole.USER, content="label these"),
                AIMessage(role=AIMessageRole.ASSISTANT, content="ok"),
            ],
            **kwargs,
        }
    )


class TestFeatures:
    def test_lists_models_and_generates(self):
        assert _client().features() == {
            AIClientFeature.GENERATION,
            AIClientFeature.MODEL_LISTING,
        }


class TestModels:
    @pytest.mark.asyncio
    async def test_lists_only_visible_models(self):
        models = await _client().list_models(_payload())

        assert [(model.id, model.name) for model in models] == [
            ("gpt-6-sol", "GPT-6 Sol"),
            ("gpt-6-mini", "GPT-6 mini"),
        ]
        assert models[0].capabilities == {
            AIModelCapability.STRUCTURED_OUTPUT,
            AIModelCapability.REASONING,
        }
        assert models[1].capabilities == {AIModelCapability.STRUCTURED_OUTPUT}

    @pytest.mark.asyncio
    async def test_unknown_or_hidden_model_is_not_found(self):
        client = _client()

        assert await client.get_model("gpt-6-internal", _payload()) is None
        assert (await client.get_model("gpt-6-mini", _payload())).id == "gpt-6-mini"

    @pytest.mark.asyncio
    async def test_catalog_is_cached_for_model_lookups(self):
        api = FakeApi()
        client = _client(api=api)

        await client.get_model("gpt-6-sol", _payload())
        await client.get_model("gpt-6-mini", _payload())

        assert len(api.calls) == 1


class TestGenerate:
    @pytest.mark.asyncio
    async def test_streams_a_plan_request_without_unsupported_fields(self):
        api = FakeApi()
        api.responses.append((200, _completed()))
        client = _client(api=api)

        await client.generate(
            _request(
                instructions="You label transactions",
                response_schema=AIJsonSchema(name="labels", schema={"type": "object"}),
                temperature=Dezimal(0),
                max_output_tokens=500,
                reasoning_effort=AIReasoningEffort.MEDIUM,
            ),
            _payload(),
        )

        method, url, headers, kwargs = api.posts()[0]
        assert (method, url) == ("POST", "https://api.openai.com/v1/responses")
        assert headers == {"Authorization": "Bearer access-1"}
        assert kwargs["json"] == {
            "model": "gpt-6-sol",
            "input": [
                {"role": "user", "content": "label these"},
                {"role": "assistant", "content": "ok"},
            ],
            "store": False,
            "stream": True,
            "instructions": "You label transactions",
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "labels",
                    "strict": True,
                    "schema": {"type": "object"},
                }
            },
            "reasoning": {"effort": "medium"},
        }

    @pytest.mark.asyncio
    async def test_models_without_reasoning_levels_omit_reasoning(self):
        api = FakeApi()
        api.responses.append((200, _completed()))

        await _client(api=api).generate(_request(model="gpt-6-mini"), _payload())

        assert "reasoning" not in api.posts()[0][3]["json"]

    @pytest.mark.asyncio
    async def test_returns_the_completed_output(self):
        api = FakeApi()
        api.responses.append(
            (200, _completed("[1]", usage={"input_tokens": 10, "output_tokens": 2}))
        )

        generation = await _client(api=api).generate(_request(), _payload())

        assert generation.status == AIGenerationStatus.COMPLETED
        assert generation.text == "[1]"
        assert generation.usage.input_tokens == 10
        assert generation.usage.output_tokens == 2

    @pytest.mark.asyncio
    async def test_incomplete_response(self):
        api = FakeApi()
        api.responses.append(
            (
                200,
                _sse(
                    {
                        "type": "response.incomplete",
                        "response": {"status": "incomplete", "output": []},
                    }
                ),
            )
        )

        generation = await _client(api=api).generate(_request(), _payload())

        assert generation.status == AIGenerationStatus.INCOMPLETE

    @pytest.mark.asyncio
    async def test_usage_limit_during_the_stream(self):
        api = FakeApi()
        api.responses.append(
            (
                200,
                _sse(
                    {
                        "type": "response.failed",
                        "response": {
                            "status": "failed",
                            "error": {
                                "code": "subscription_sharing_usage_limit_exceeded",
                                "message": "Usage limit reached",
                            },
                        },
                    }
                ),
            )
        )

        with pytest.raises(AIProviderError) as error:
            await _client(api=api).generate(_request(), _payload())

        assert error.value.code == AIProviderErrorCode.INSUFFICIENT_FUNDS

    @pytest.mark.asyncio
    async def test_interrupted_stream_is_unavailable(self):
        api = FakeApi()
        api.responses.append(
            (200, _sse({"type": "response.output_text.delta", "delta": "{"}))
        )

        with pytest.raises(AIProviderError) as error:
            await _client(api=api).generate(_request(), _payload())

        assert error.value.code == AIProviderErrorCode.UNAVAILABLE

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "status,body,code",
        [
            (
                429,
                {"error": {"code": "subscription_sharing_usage_limit_exceeded"}},
                AIProviderErrorCode.INSUFFICIENT_FUNDS,
            ),
            (
                403,
                {"error": {"code": "subscription_sharing_user_not_eligible"}},
                AIProviderErrorCode.INVALID_CREDENTIALS,
            ),
            (
                403,
                {"detail": "Not available in your region"},
                AIProviderErrorCode.INVALID_CREDENTIALS,
            ),
            (
                400,
                {
                    "error": {
                        "code": "subscription_sharing_unsupported_capability",
                        "param": "text.format",
                    }
                },
                AIProviderErrorCode.UNSUPPORTED_OPERATION,
            ),
            (
                404,
                {"error": {"code": "model_not_found"}},
                AIProviderErrorCode.MODEL_NOT_FOUND,
            ),
        ],
        ids=["usage-limit", "not-eligible", "policy", "unsupported", "model"],
    )
    async def test_maps_request_errors(self, status, body, code):
        api = FakeApi()
        api.responses.append((status, body))

        with pytest.raises(AIProviderError) as error:
            await _client(api=api).generate(_request(), _payload())

        assert error.value.code == code
        assert len(api.posts()) == 1

    @pytest.mark.asyncio
    async def test_temporary_failures_are_retried_then_unavailable(self):
        api = FakeApi()
        api.responses.extend(
            [(503, {"detail": "unavailable"})] * (ChatGPTClient.MAX_RETRIES + 1)
        )
        port = FakePort(_payload())

        with pytest.raises(AIProviderError) as error:
            await _client(port=port, api=api).generate(_request(), _payload())

        assert error.value.code == AIProviderErrorCode.UNAVAILABLE
        assert len(api.posts()) == ChatGPTClient.MAX_RETRIES + 1
        assert port.status == "ON"

    @pytest.mark.asyncio
    async def test_unknown_model_is_not_found(self):
        with pytest.raises(AIProviderError) as error:
            await _client().generate(_request(model="gpt-1"), _payload())

        assert error.value.code == AIProviderErrorCode.MODEL_NOT_FOUND

    @pytest.mark.asyncio
    async def test_upstream_providers_are_unsupported(self):
        with pytest.raises(AIProviderError) as error:
            await _client().generate(_request(upstream_provider="azure"), _payload())

        assert error.value.code == AIProviderErrorCode.UNSUPPORTED_OPERATION

    @pytest.mark.asyncio
    async def test_requires_a_connected_account(self):
        with pytest.raises(AIProviderError) as error:
            await _client().generate(_request(), None)

        assert error.value.code == AIProviderErrorCode.INVALID_CREDENTIALS


class TestSession:
    @pytest.mark.asyncio
    async def test_refreshes_near_expiry_and_saves_the_rotation(self):
        stale = _payload(expires_at=(NOW + timedelta(minutes=2)).isoformat())
        fresh = _payload("access-2", "refresh-2")
        port = FakePort(stale)
        oauth = FakeOAuth()
        oauth.refresh_results.append(fresh)
        api = FakeApi()
        api.responses.append((200, _completed()))

        await _client(port, oauth, api).generate(_request(), stale)

        assert oauth.refreshed == [stale]
        assert port.updates == [fresh]
        assert api.posts()[0][2] == {"Authorization": "Bearer access-2"}

    @pytest.mark.asyncio
    async def test_waits_for_the_earliest_refresh_time(self):
        payload = _payload(
            expires_at=(NOW + timedelta(minutes=2)).isoformat(),
            refresh_after=(NOW + timedelta(minutes=1)).isoformat(),
        )
        oauth = FakeOAuth()
        api = FakeApi()
        api.responses.append((200, _completed()))

        await _client(FakePort(payload), oauth, api).generate(_request(), payload)

        assert oauth.refreshed == []

    @pytest.mark.asyncio
    async def test_concurrent_requests_refresh_once(self):
        stale = _payload(expires_at=(NOW + timedelta(minutes=2)).isoformat())
        fresh = _payload("access-2", "refresh-2")
        port = FakePort(stale)
        oauth = FakeOAuth()
        oauth.refresh_results.append(fresh)
        api = FakeApi()
        api.responses.extend([(200, _completed()), (200, _completed())])
        client = _client(port, oauth, api)

        await asyncio.gather(
            client.generate(_request(), stale), client.generate(_request(), stale)
        )

        assert len(oauth.refreshed) == 1
        assert [call[2] for call in api.posts()] == [
            {"Authorization": "Bearer access-2"}
        ] * 2

    @pytest.mark.asyncio
    async def test_uses_tokens_rotated_by_another_device(self):
        stale = _payload(expires_at=(NOW + timedelta(minutes=2)).isoformat())
        synced = _payload("access-9", "refresh-9")
        oauth = FakeOAuth()
        api = FakeApi()
        api.responses.append((200, _completed()))

        await _client(FakePort(synced), oauth, api).generate(_request(), stale)

        assert oauth.refreshed == []
        assert api.posts()[0][2] == {"Authorization": "Bearer access-9"}

    @pytest.mark.asyncio
    async def test_rejected_token_is_refreshed_and_retried_once(self):
        payload = _payload()
        fresh = _payload("access-2", "refresh-2")
        port = FakePort(payload)
        oauth = FakeOAuth()
        oauth.refresh_results.append(fresh)
        api = FakeApi()
        api.rejected_tokens.add("access-1")
        api.responses.append((200, _completed()))

        generation = await _client(port, oauth, api).generate(_request(), payload)

        assert generation.status == AIGenerationStatus.COMPLETED
        assert oauth.refreshed == [payload]
        assert port.status == "ON"

    @pytest.mark.asyncio
    async def test_rejected_after_refresh_marks_the_sign_in_expired(self):
        payload = _payload()
        port = FakePort(payload)
        oauth = FakeOAuth()
        oauth.refresh_results.append(_payload("access-2", "refresh-2"))
        api = FakeApi()
        api.rejected_tokens.update({"access-1", "access-2"})

        with pytest.raises(AIProviderError) as error:
            await _client(port, oauth, api).generate(_request(), payload)

        assert error.value.code == AIProviderErrorCode.REAUTHENTICATION_REQUIRED
        assert port.status == "EXPIRED"
        assert len(oauth.refreshed) == 1

    @pytest.mark.asyncio
    async def test_reused_refresh_token_marks_the_sign_in_expired(self):
        stale = _payload(expires_at=(NOW - timedelta(minutes=1)).isoformat())
        port = FakePort(stale)
        oauth = FakeOAuth()
        oauth.refresh_results.append(
            AIProviderError(AIProviderErrorCode.REAUTHENTICATION_REQUIRED, "reused")
        )

        with pytest.raises(AIProviderError) as error:
            await _client(port, oauth).generate(_request(), stale)

        assert error.value.code == AIProviderErrorCode.REAUTHENTICATION_REQUIRED
        assert port.status == "EXPIRED"
        assert port.payload == stale

    @pytest.mark.asyncio
    async def test_temporary_refresh_failure_keeps_a_valid_token(self):
        payload = _payload(expires_at=(NOW + timedelta(minutes=2)).isoformat())
        port = FakePort(payload)
        oauth = FakeOAuth()
        oauth.refresh_results.append(
            AIProviderError(AIProviderErrorCode.UNAVAILABLE, "offline")
        )
        api = FakeApi()
        api.responses.append((200, _completed()))

        await _client(port, oauth, api).generate(_request(), payload)

        assert api.posts()[0][2] == {"Authorization": "Bearer access-1"}
        assert port.status == "ON"

    @pytest.mark.asyncio
    async def test_temporary_refresh_failure_with_an_expired_token_fails(self):
        payload = _payload(expires_at=(NOW - timedelta(minutes=1)).isoformat())
        port = FakePort(payload)
        oauth = FakeOAuth()
        oauth.refresh_results.append(
            AIProviderError(AIProviderErrorCode.UNAVAILABLE, "offline")
        )

        with pytest.raises(AIProviderError) as error:
            await _client(port, oauth).generate(_request(), payload)

        assert error.value.code == AIProviderErrorCode.UNAVAILABLE
        assert port.status == "ON"


class TestConnection:
    @pytest.mark.asyncio
    async def test_starts_with_the_expired_registration(self):
        previous = _payload(id_token="old")
        port = FakePort(previous)
        port.status = "EXPIRED"
        oauth = FakeOAuth()

        await _client(port, oauth).start_authorization({}, "finanze://complete")

        assert oauth.started == [("finanze://complete", previous)]

    @pytest.mark.asyncio
    async def test_completion_checks_plan_access(self):
        api = FakeApi()
        client = _client(FakePort(), api=api)

        payload = await client.complete_authorization(
            CompleteExternalIntegrationConnectionRequest(CHATGPT, "state", "code")
        )
        await client.get_model("gpt-6-sol", payload)

        assert payload == _payload()
        assert len(api.calls) == 1

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "status,body,code",
        [
            (
                403,
                {"error": {"code": "subscription_sharing_user_not_eligible"}},
                IntegrationSetupErrorCode.NOT_ENTITLED,
            ),
            (
                401,
                {"detail": "Unauthorized"},
                IntegrationSetupErrorCode.INVALID_CREDENTIALS,
            ),
            (503, {"detail": "Unavailable"}, IntegrationSetupErrorCode.UNREACHABLE),
        ],
    )
    async def test_completion_rejects_accounts_without_plan_access(
        self, status, body, code
    ):
        api = FakeApi()
        api.models = (status, body)

        with pytest.raises(IntegrationSetupError) as error:
            await _client(FakePort(), api=api).complete_authorization(
                CompleteExternalIntegrationConnectionRequest(CHATGPT, "state", "code")
            )

        assert error.value.code == code

    @pytest.mark.asyncio
    async def test_callback_destination_comes_from_the_pending_sign_in(self):
        client = _client()

        assert await client.callback_destination("known") == (
            "finanze://integration/complete"
        )
        assert await client.callback_destination("unknown") is None

    @pytest.mark.asyncio
    async def test_teardown_revokes_the_stored_session(self):
        oauth = FakeOAuth()
        client = _client(oauth=oauth)

        await client.teardown(_payload())
        await client.teardown(None)

        assert oauth.revoked == [_payload()]
