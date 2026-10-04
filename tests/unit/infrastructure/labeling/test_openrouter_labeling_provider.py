import json
from datetime import date
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.dezimal import Dezimal
from domain.external_labeling import (
    ExternalLabelCandidate,
    ExternalLabelingExample,
    ExternalLabelingRequest,
    ExternalLabelingTx,
)
from domain.transactions import TxType
from infrastructure.labeling.openrouter_labeling_provider import (
    DECISIONS_BATCH_SIZE,
    OpenRouterLabelingProvider,
)

CREDENTIALS = {"api_key": "sk-test"}
DECISIONS_INFO = {
    "name": "Jev",
    "architecture": {"output_modalities": ["decisions"]},
    "supported_parameters": [],
}
CHAT_INFO = {
    "name": "Chat model",
    "architecture": {"output_modalities": ["text"]},
    "supported_parameters": ["structured_outputs", "temperature"],
}
ENDPOINTS = {
    "endpoints": [
        {
            "tag": "openai",
            "supported_parameters": ["response_format", "temperature"],
        },
        {
            "tag": "openai/flex",
            "supported_parameters": ["structured_outputs"],
        },
        {"tag": "deepinfra/fp8", "supported_parameters": ["temperature"]},
    ]
}


def _tx(name="MERCADONA 123", tx_type=TxType.OUTFLOW, counterparty=None):
    return ExternalLabelingTx(
        id=uuid4(),
        date=date(2026, 9, 1),
        type=tx_type,
        amount=Dezimal("-42.10"),
        currency="EUR",
        name=name,
        counterparty=counterparty,
    )


def _provider(info):
    client = MagicMock()
    client.get_model = AsyncMock(return_value=info)
    client.get_model_endpoints = AsyncMock(return_value=ENDPOINTS)
    client.systemone = AsyncMock()
    client.chat_completion = AsyncMock()
    return OpenRouterLabelingProvider(client), client


def _labels():
    return [
        ExternalLabelCandidate(id=uuid4(), key="groceries"),
        ExternalLabelCandidate(
            id=uuid4(), name="Padel club", description="Court bookings"
        ),
    ]


class TestGetModel:
    @pytest.mark.asyncio
    async def test_decisions_model_is_probabilistic(self):
        provider, _ = _provider(DECISIONS_INFO)

        model = await provider.get_model("~typesafe/jev-latest", CREDENTIALS)

        assert model.probabilistic
        assert model.name == "Jev"

    @pytest.mark.asyncio
    async def test_chat_model_requires_structured_output(self):
        provider, _ = _provider(
            {
                "architecture": {"output_modalities": ["text"]},
                "supported_parameters": [],
            }
        )

        assert await provider.get_model("some/model", CREDENTIALS) is None

    @pytest.mark.asyncio
    async def test_unknown_model(self):
        provider, _ = _provider(None)

        assert await provider.get_model("missing/model", CREDENTIALS) is None

    @pytest.mark.asyncio
    async def test_model_info_is_cached(self):
        provider, client = _provider(CHAT_INFO)

        await provider.get_model("some/model", CREDENTIALS)
        await provider.get_model("some/model", CREDENTIALS)

        assert client.get_model.await_count == 1

    @pytest.mark.asyncio
    @pytest.mark.parametrize("upstream", ["openai/flex", "OpenAI", "openai"])
    async def test_upstream_provider_available(self, upstream):
        provider, client = _provider(CHAT_INFO)

        model = await provider.get_model("openai/gpt-x", CREDENTIALS, upstream)

        assert model is not None
        client.get_model_endpoints.assert_awaited_once_with("openai/gpt-x", "sk-test")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("upstream", ["azure", "deepinfra/fp8", "flex"])
    async def test_upstream_provider_missing_or_without_structured_output(
        self, upstream
    ):
        provider, _ = _provider(CHAT_INFO)

        assert await provider.get_model("openai/gpt-x", CREDENTIALS, upstream) is None

    @pytest.mark.asyncio
    async def test_upstream_provider_not_allowed_for_decisions_model(self):
        provider, client = _provider(DECISIONS_INFO)

        assert (
            await provider.get_model("~typesafe/jev-latest", CREDENTIALS, "openai")
            is None
        )
        client.get_model_endpoints.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_upstream_provider_endpoints_failure(self):
        provider, client = _provider(CHAT_INFO)
        client.get_model_endpoints.side_effect = RuntimeError("down")

        assert (
            await provider.get_model("openai/gpt-x", CREDENTIALS, "openai/flex") is None
        )


class TestLabelWithDecisions:
    @pytest.mark.asyncio
    async def test_maps_choices_and_confidence(self):
        provider, client = _provider(DECISIONS_INFO)
        labels = _labels()
        first, second = _tx(), _tx("PADEL INDOOR", counterparty="Padel Club SL")
        client.systemone.return_value = {
            "answers": {
                "m1": {"type": "choice", "choice": "groceries", "confidence": 0.93},
                "m2": {
                    "type": "choice",
                    "choice": "custom_padel_club",
                    "probabilities": {"custom_padel_club": 0.7, "none": 0.3},
                },
            }
        }

        suggestions = await provider.label(
            ExternalLabelingRequest(
                model="~typesafe/jev-latest", txs=[first, second], labels=labels
            ),
            CREDENTIALS,
        )

        assert [(s.tx_id, s.label_id, s.confidence) for s in suggestions] == [
            (first.id, labels[0].id, Dezimal("0.93")),
            (second.id, labels[1].id, Dezimal("0.7")),
        ]
        body = client.systemone.await_args.args[0]
        assert body["model"] == "~typesafe/jev-latest"
        categories = body["state"]["categories"]
        assert set(categories) == {"groceries", "custom_padel_club", "none"}
        assert all(categories.values())
        for question in body["questions"].values():
            assert question["criteria"] == dict.fromkeys(categories)
        serialized = json.dumps(body)
        for description in categories.values():
            assert serialized.count(json.dumps(description)) == 1
        movement = body["state"]["movements"]["m2"]
        assert movement["direction"] == "outgoing"
        assert movement["amount"] == "42.10 EUR"
        assert movement["counterparty"] == "Padel Club SL"
        assert client.systemone.await_args.args[1] == "sk-test"

    @pytest.mark.asyncio
    async def test_none_choice_is_ignored(self):
        provider, client = _provider(DECISIONS_INFO)
        client.systemone.return_value = {
            "answers": {"m1": {"type": "choice", "choice": "none", "confidence": 0.9}}
        }

        suggestions = await provider.label(
            ExternalLabelingRequest(
                model="~typesafe/jev-latest", txs=[_tx()], labels=_labels()
            ),
            CREDENTIALS,
        )

        assert suggestions == []

    @pytest.mark.asyncio
    async def test_batches_movements(self):
        provider, client = _provider(DECISIONS_INFO)
        client.systemone.return_value = {"answers": {}}

        await provider.label(
            ExternalLabelingRequest(
                model="~typesafe/jev-latest",
                txs=[_tx() for _ in range(DECISIONS_BATCH_SIZE + 1)],
                labels=_labels(),
            ),
            CREDENTIALS,
        )

        assert client.systemone.await_count == 2

    @pytest.mark.asyncio
    async def test_falls_back_to_decisions_by_model_prefix(self):
        provider, client = _provider(None)
        client.get_model.side_effect = RuntimeError("down")
        client.systemone.return_value = {"answers": {}}

        await provider.label(
            ExternalLabelingRequest(
                model="typesafe/jev-1.13", txs=[_tx()], labels=_labels()
            ),
            CREDENTIALS,
        )

        client.systemone.assert_awaited_once()
        client.chat_completion.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_adds_user_instructions_to_context(self):
        provider, client = _provider(DECISIONS_INFO)
        client.systemone.return_value = {"answers": {}}

        await provider.label(
            ExternalLabelingRequest(
                model="~typesafe/jev-latest",
                txs=[_tx()],
                labels=_labels(),
                instructions="Bizum from Ana is rent",
            ),
            CREDENTIALS,
        )

        context = client.systemone.await_args.args[0]["state"]["context"]
        assert context.endswith("User guidance: Bizum from Ana is rent")


class TestLabelWithChat:
    @pytest.mark.asyncio
    async def test_parses_structured_response(self):
        provider, client = _provider(CHAT_INFO)
        labels = _labels()
        tx = _tx(tx_type=TxType.INFLOW)
        example_tx = _tx("LIDL")
        client.chat_completion.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "results": [
                                    {
                                        "id": "m1",
                                        "category": "groceries",
                                        "confidence": 1.4,
                                    },
                                    {"id": "m9", "category": "groceries"},
                                ]
                            }
                        )
                    }
                }
            ]
        }

        suggestions = await provider.label(
            ExternalLabelingRequest(
                model="some/model",
                txs=[tx],
                labels=labels,
                examples=[
                    ExternalLabelingExample(tx=example_tx, label_ids=[labels[0].id])
                ],
            ),
            CREDENTIALS,
        )

        assert [(s.tx_id, s.label_id, s.confidence) for s in suggestions] == [
            (tx.id, labels[0].id, Dezimal(1))
        ]
        body = client.chat_completion.await_args.args[0]
        assert body["response_format"]["type"] == "json_schema"
        assert "LIDL" in body["messages"][0]["content"]
        assert json.loads(body["messages"][1]["content"])["m1"]["direction"] == (
            "incoming"
        )

    @pytest.mark.asyncio
    async def test_adds_user_instructions_to_system_prompt(self):
        provider, client = _provider(CHAT_INFO)
        client.chat_completion.return_value = {
            "choices": [{"message": {"content": json.dumps({"results": []})}}]
        }

        await provider.label(
            ExternalLabelingRequest(
                model="some/model",
                txs=[_tx()],
                labels=_labels(),
                instructions="Padel is leisure",
            ),
            CREDENTIALS,
        )

        system_prompt = client.chat_completion.await_args.args[0]["messages"][0][
            "content"
        ]
        assert system_prompt.endswith(
            "Additional guidance from the user:\nPadel is leisure"
        )

    @pytest.mark.asyncio
    async def test_routes_to_upstream_provider_without_fallbacks(self):
        provider, client = _provider(CHAT_INFO)
        client.chat_completion.return_value = {
            "choices": [{"message": {"content": json.dumps({"results": []})}}]
        }

        await provider.label(
            ExternalLabelingRequest(
                model="openai/gpt-x",
                txs=[_tx()],
                labels=_labels(),
                upstream_provider="openai/flex",
            ),
            CREDENTIALS,
        )

        body = client.chat_completion.await_args.args[0]
        assert body["provider"] == {
            "order": ["openai/flex"],
            "allow_fallbacks": False,
        }

    @pytest.mark.asyncio
    async def test_no_routing_without_upstream_provider(self):
        provider, client = _provider(CHAT_INFO)
        client.chat_completion.return_value = {
            "choices": [{"message": {"content": json.dumps({"results": []})}}]
        }

        await provider.label(
            ExternalLabelingRequest(model="some/model", txs=[_tx()], labels=_labels()),
            CREDENTIALS,
        )

        assert "provider" not in client.chat_completion.await_args.args[0]

    @pytest.mark.asyncio
    async def test_invalid_json_returns_no_suggestions(self):
        provider, client = _provider(CHAT_INFO)
        client.chat_completion.return_value = {
            "choices": [{"message": {"content": "not json"}}]
        }

        suggestions = await provider.label(
            ExternalLabelingRequest(model="some/model", txs=[_tx()], labels=_labels()),
            CREDENTIALS,
        )

        assert suggestions == []


@pytest.mark.asyncio
async def test_empty_request_skips_calls():
    provider, client = _provider(DECISIONS_INFO)

    assert (
        await provider.label(
            ExternalLabelingRequest(model="x/y", txs=[], labels=_labels()),
            CREDENTIALS,
        )
        == []
    )
    client.get_model.assert_not_awaited()
