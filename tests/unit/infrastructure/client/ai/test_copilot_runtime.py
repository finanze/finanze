from types import SimpleNamespace

import pytest
from copilot.rpc import (
    ModelBilling,
    ModelPolicyState,
    PermissionDecisionReject,
    TokenPriceUnit,
)
from copilot.session_events import AssistantMessageData, SessionErrorData
from domain.ai import AIModelPricing
from domain.dezimal import Dezimal
from infrastructure.agent_runtime.runtime_sandbox import AgentRuntimeSandbox
from infrastructure.client.ai.github_copilot import copilot_runtime
from infrastructure.client.ai.github_copilot.copilot_runtime import CopilotRuntime
from infrastructure.client.ai.github_copilot.copilot_runtime_types import (
    CopilotErrorKind,
    CopilotModelEntry,
    CopilotRuntimeError,
)

SCHEMA = {"type": "object"}


class FakeSession:
    def __init__(self, client: "FakeClient"):
        self.client = client
        self.session_id = "session-1"
        self.handlers = []
        self.disconnected = False

    def on(self, handler):
        self.handlers.append(handler)
        return lambda: None

    async def send_and_wait(self, prompt, response_schema=None, timeout=None):
        self.client.sent.append((prompt, response_schema, timeout))
        for data in self.client.events:
            for handler in self.handlers:
                handler(SimpleNamespace(data=data))
        if self.client.send_error:
            raise self.client.send_error
        return self.client.response

    async def disconnect(self):
        self.disconnected = True


class FakeClient:
    def __init__(self, **options):
        self.options = options
        self.start_error = None
        self.stop_error = None
        self.send_error = None
        self.events = []
        self.sent = []
        self.sessions = []
        self.deleted = []
        self.session_options = None
        self.force_stopped = False
        self.stopped = False
        self.models = []
        self.units = []
        self.units_error = None
        self.response = SimpleNamespace(
            data=AssistantMessageData(content='{"labels": []}', message_id="m")
        )
        self.rpc = SimpleNamespace(
            models=SimpleNamespace(
                list=self._list_models,
                list_token_price_units=self._list_token_price_units,
            )
        )

    async def _list_models(self, request, timeout=None):
        return SimpleNamespace(models=self.models)

    async def _list_token_price_units(self, request, timeout=None):
        if self.units_error:
            raise self.units_error
        return SimpleNamespace(
            units=[
                SimpleNamespace(model_id=model_id, unit=unit)
                for model_id, unit in self.units
            ]
        )

    async def start(self):
        if self.start_error:
            raise self.start_error

    async def stop(self):
        self.stopped = True
        if self.stop_error:
            raise self.stop_error

    async def force_stop(self):
        self.force_stopped = True

    async def get_auth_status(self):
        return SimpleNamespace(isAuthenticated=True)

    async def create_session(self, **options):
        self.session_options = options
        session = FakeSession(self)
        self.sessions.append(session)
        return session

    async def delete_session(self, session_id):
        self.deleted.append(session_id)


@pytest.fixture
def created(monkeypatch):
    clients = []

    def factory(**options):
        client = FakeClient(**options)
        clients.append(client)
        return client

    monkeypatch.setattr(copilot_runtime, "CopilotClient", factory)
    return clients


async def _runtime(tmp_path, created) -> tuple[CopilotRuntime, FakeClient]:
    dirs = await AgentRuntimeSandbox(tmp_path).create_instance("copilot")
    runtime = await CopilotRuntime.start("/runtime/copilot", "gho_token", dirs)
    return runtime, created[-1]


def _model(model_id, state=ModelPolicyState.ENABLED, efforts=None, billing=None):
    return SimpleNamespace(
        id=model_id,
        name=model_id.upper(),
        policy=SimpleNamespace(state=state) if state else None,
        capabilities=SimpleNamespace(
            supports=SimpleNamespace(reasoning_effort=efforts is not None)
        ),
        supported_reasoning_efforts=efforts,
        billing=ModelBilling.from_dict(billing) if billing is not None else None,
    )


def _token_prices(batch_size, input_price, output_price, multiplier=None):
    billing = {
        "tokenPrices": {
            "batchSize": batch_size,
            "inputPrice": input_price,
            "outputPrice": output_price,
        }
    }
    if multiplier is not None:
        billing["multiplier"] = multiplier
    return billing


@pytest.mark.asyncio
async def test_start_uses_isolated_token_only_client(tmp_path, created, monkeypatch):
    monkeypatch.setenv("GH_TOKEN", "ambient")
    monkeypatch.setenv("GITHUB_TOKEN", "ambient")
    monkeypatch.setenv("COPILOT_GITHUB_TOKEN", "ambient")

    runtime, client = await _runtime(tmp_path, created)

    options = client.options
    assert options["connection"].path == "/runtime/copilot"
    assert options["github_token"] == "gho_token"
    assert options["use_logged_in_user"] is False
    assert options["mode"] == "empty"
    assert options["base_directory"] == str(runtime._dirs.home)
    assert options["working_directory"] == str(runtime._dirs.work)
    assert options["client_info"] == {"application_name": "Finanze"}
    env = options["env"]
    assert env["COPILOT_GITHUB_TELEMETRY_DISABLED"] == "true"
    assert not {"GH_TOKEN", "GITHUB_TOKEN", "COPILOT_GITHUB_TOKEN"} & env.keys()


@pytest.mark.asyncio
async def test_failed_start_force_stops(tmp_path, monkeypatch):
    client = FakeClient()
    client.start_error = OSError("spawn failed")
    monkeypatch.setattr(copilot_runtime, "CopilotClient", lambda **options: client)
    dirs = await AgentRuntimeSandbox(tmp_path).create_instance("copilot")

    with pytest.raises(CopilotRuntimeError) as error:
        await CopilotRuntime.start("/runtime/copilot", "gho_token", dirs)

    assert error.value.kind == CopilotErrorKind.RUNTIME
    assert client.force_stopped


@pytest.mark.asyncio
async def test_complete_runs_locked_down_session_and_deletes_it(tmp_path, created):
    runtime, client = await _runtime(tmp_path, created)

    text = await runtime.complete(
        model="gpt-5-mini",
        instructions="Label",
        prompt="movements",
        schema=SCHEMA,
        reasoning_effort="low",
        timeout=30,
    )

    assert text == '{"labels": []}'
    options = client.session_options
    assert options["model"] == "gpt-5-mini"
    assert options["available_tools"] == []
    assert options["system_message"] == {"mode": "replace", "content": "Label"}
    assert options["infinite_sessions"] == {"enabled": False}
    assert options["reasoning_effort"] == "low"
    assert options["streaming"] is False
    assert options["working_directory"] == str(runtime._dirs.work)
    decision = options["on_permission_request"](object(), {})
    assert isinstance(decision, PermissionDecisionReject)
    assert client.sent == [("movements", SCHEMA, 30)]
    assert client.sessions[0].disconnected
    assert client.deleted == ["session-1"]


@pytest.mark.asyncio
async def test_complete_classifies_session_errors_and_cleans_up(tmp_path, created):
    runtime, client = await _runtime(tmp_path, created)
    client.events = [
        SessionErrorData(
            error_type="quota", message="Premium request limit", status_code=402
        )
    ]
    client.send_error = RuntimeError("Session aborted before structured output")

    with pytest.raises(CopilotRuntimeError) as error:
        await runtime.complete("gpt-5-mini", None, "movements", SCHEMA, None, 30)

    assert error.value.kind == CopilotErrorKind.QUOTA
    assert client.deleted == ["session-1"]


@pytest.mark.asyncio
async def test_complete_without_assistant_message_returns_none(tmp_path, created):
    runtime, client = await _runtime(tmp_path, created)
    client.response = None

    assert await runtime.complete("m", None, "p", SCHEMA, None, 30) is None


@pytest.mark.asyncio
async def test_list_models_maps_policy_and_efforts(tmp_path, created):
    runtime, client = await _runtime(tmp_path, created)
    client.models = [
        _model("enabled", efforts=["low", "high"]),
        _model("disabled", state=ModelPolicyState.DISABLED),
        _model("unconfigured", state=ModelPolicyState.UNCONFIGURED),
        _model("no-policy", state=None),
    ]

    entries = await runtime.list_models()

    assert entries == [
        CopilotModelEntry(
            id="enabled",
            name="ENABLED",
            enabled=True,
            reasoning_efforts=("low", "high"),
        ),
        CopilotModelEntry(id="disabled", name="DISABLED", enabled=False),
        CopilotModelEntry(id="unconfigured", name="UNCONFIGURED", enabled=False),
        CopilotModelEntry(id="no-policy", name="NO-POLICY", enabled=True),
    ]


@pytest.mark.asyncio
async def test_list_models_converts_token_prices_to_usd_per_million(tmp_path, created):
    runtime, client = await _runtime(tmp_path, created)
    client.models = [
        _model("credits", billing=_token_prices(1_000_000, 10.0, 50.0, 0.33)),
        _model("nano", billing=_token_prices(1_000, 2_000_000.0, 12_500_000.0)),
        _model("legacy", billing={"multiplier": 1.0}),
        _model("unitless", billing=_token_prices(1_000_000, 10.0, 50.0)),
        _model("no-batch", billing=_token_prices(None, 10.0, 50.0)),
    ]
    client.units = [
        ("credits", TokenPriceUnit.AI_CREDITS),
        ("nano", TokenPriceUnit.NANO_AIU),
        ("no-batch", TokenPriceUnit.AI_CREDITS),
    ]

    pricing = {entry.id: entry.pricing for entry in await runtime.list_models()}

    assert pricing == {
        "credits": AIModelPricing(
            input_per_million=Dezimal("0.1"), output_per_million=Dezimal("0.5")
        ),
        "nano": AIModelPricing(
            input_per_million=Dezimal("0.02"), output_per_million=Dezimal("0.125")
        ),
        "legacy": None,
        "unitless": None,
        "no-batch": None,
    }


@pytest.mark.asyncio
async def test_list_models_without_price_units_keeps_catalog(tmp_path, created):
    runtime, client = await _runtime(tmp_path, created)
    client.models = [_model("credits", billing=_token_prices(1_000_000, 10.0, 50.0))]
    client.units_error = RuntimeError("unsupported")

    entries = await runtime.list_models()

    assert entries == [CopilotModelEntry(id="credits", name="CREDITS", enabled=True)]


@pytest.mark.asyncio
async def test_stop_falls_back_to_force_stop_and_removes_dirs(tmp_path, created):
    runtime, client = await _runtime(tmp_path, created)
    client.stop_error = ExceptionGroup("stop", [RuntimeError("busy")])

    await runtime.stop()

    assert client.stopped
    assert client.force_stopped
    assert not runtime._dirs.root.exists()
