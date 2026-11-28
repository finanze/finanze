import json
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest

from domain.data_init import MigrationAheadOfTime
from domain.exception.exceptions import (
    UnsupportedBackupProtocol,
    UnsupportedBackupVersion,
)
from domain.exception.reporting import is_reportable
from domain.telemetry import TelemetryLevel


_MOBILE_ROOT = Path(__file__).resolve().parents[3] / "frontend/app/src/python/finanze"
_MODULE_PATH = _MOBILE_ROOT / "infrastructure/telemetry/bridge_error_reporter.py"


def _load_module():
    stub = ModuleType("js")
    previous = sys.modules.get("js")
    sys.modules["js"] = stub
    try:
        spec = spec_from_file_location("mobile_bridge_error_reporter", _MODULE_PATH)
        assert spec is not None and spec.loader is not None
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if previous is None:
            del sys.modules["js"]
        else:
            sys.modules["js"] = previous


_MODULE = _load_module()


def _raise_chain():
    try:
        try:
            raise ValueError("no such column: foo")
        except ValueError as inner:
            raise RuntimeError("migration add_foo failed") from inner
    except RuntimeError as outer:
        return outer


class TestCauseChain:
    def test_walks_explicit_causes(self):
        chain = _MODULE._cause_chain(_raise_chain())

        assert [type(e).__name__ for e in chain] == ["RuntimeError", "ValueError"]

    def test_walks_implicit_context(self):
        try:
            try:
                raise KeyError("missing")
            except KeyError:
                raise TypeError("boom")
        except TypeError as exc:
            chain = _MODULE._cause_chain(exc)

        assert [type(e).__name__ for e in chain] == ["TypeError", "KeyError"]

    def test_ignores_suppressed_context(self):
        try:
            try:
                raise KeyError("missing")
            except KeyError:
                raise TypeError("boom") from None
        except TypeError as exc:
            chain = _MODULE._cause_chain(exc)

        assert [type(e).__name__ for e in chain] == ["TypeError"]

    def test_respects_depth_cap(self):
        exc = Exception("level-0")
        for level in range(1, 10):
            nxt = Exception(f"level-{level}")
            nxt.__cause__ = exc
            exc = nxt

        chain = _MODULE._cause_chain(exc)

        assert len(chain) == _MODULE.MAX_CAUSES + 1

    def test_terminates_on_cycles(self):
        first = Exception("first")
        second = Exception("second")
        first.__cause__ = second
        second.__cause__ = first

        chain = _MODULE._cause_chain(first)

        assert [str(e) for e in chain] == ["first", "second"]


class TestBuildPayload:
    def _build(self, exc):
        reporter = _MODULE.BridgeErrorReporter()
        return reporter._build_payload(exc, None, None, TelemetryLevel.ERROR)

    def test_includes_causes_root_first(self):
        payload = self._build(_raise_chain())

        assert payload["type"] == "RuntimeError"
        assert payload["value"] == "migration add_foo failed"
        assert [c["type"] for c in payload["causes"]] == ["ValueError"]
        assert payload["causes"][0]["value"] == "no such column: foo"

    def test_orders_multiple_causes_root_first(self):
        root = Exception("root")
        middle = Exception("middle")
        middle.__cause__ = root
        outer = Exception("outer")
        outer.__cause__ = middle

        payload = self._build(outer)

        assert [c["value"] for c in payload["causes"]] == ["root", "middle"]

    def test_omits_causes_when_there_are_none(self):
        payload = self._build(ValueError("standalone"))

        assert "causes" not in payload
        assert payload["type"] == "ValueError"


def _load_mobile_module(name: str, path: Path):
    spec = spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def mobile_router(monkeypatch):
    quart = _load_mobile_module("mobile_quart", _MOBILE_ROOT / "quart.py")
    wrapper = _load_mobile_module(
        "mobile_request_wrapper",
        _MOBILE_ROOT / "infrastructure/controller/request_wrapper.py",
    )
    monkeypatch.setitem(sys.modules, "quart", quart)
    monkeypatch.setitem(
        sys.modules, "infrastructure.controller.request_wrapper", wrapper
    )
    handler = _load_mobile_module(
        "mobile_handler", _MOBILE_ROOT / "infrastructure/controller/handler.py"
    )
    monkeypatch.setitem(sys.modules, "infrastructure.controller.handler", handler)
    router_mod = _load_mobile_module(
        "mobile_router", _MOBILE_ROOT / "infrastructure/controller/router.py"
    )
    return router_mod.Router()


class TestBackupExceptionFiltering:
    @pytest.mark.parametrize(
        "exc",
        [
            UnsupportedBackupVersion(remote_schema_revision=96),
            MigrationAheadOfTime("v99.0.0:0_future"),
            UnsupportedBackupProtocol(99),
        ],
    )
    def test_backup_version_exceptions_are_not_reportable_or_captured(
        self, monkeypatch, exc
    ):
        assert is_reportable(exc) is False

        capture_mock = Mock()
        js_stub = ModuleType("js")
        js_stub.jsBridge = SimpleNamespace(
            telemetry=SimpleNamespace(capture=capture_mock, environment="test")
        )
        monkeypatch.setattr(_MODULE, "js", js_stub)

        reporter = _MODULE.BridgeErrorReporter()
        reporter.set_enabled(True)
        reporter.capture_exception(exc)

        capture_mock.assert_not_called()

    def test_unexpected_exception_is_captured_when_enabled(self, monkeypatch):
        capture_mock = Mock()
        js_stub = ModuleType("js")
        js_stub.jsBridge = SimpleNamespace(
            telemetry=SimpleNamespace(capture=capture_mock, environment="test")
        )
        monkeypatch.setattr(_MODULE, "js", js_stub)

        reporter = _MODULE.BridgeErrorReporter()
        reporter.set_enabled(True)
        reporter.capture_exception(RuntimeError("unexpected failure"))

        capture_mock.assert_called_once()


class TestMobileHandlerBackupExceptions:
    @pytest.mark.asyncio
    async def test_unsupported_backup_version_returns_409_with_details(
        self, mobile_router
    ):
        reporter = Mock()
        mobile_router.error_reporter = reporter

        async def route(_request):
            raise UnsupportedBackupVersion(remote_schema_revision=96)

        mobile_router.add("POST", "/api/v1/cloud/backup/import", route)
        response = await mobile_router.handle(
            "POST", "/api/v1/cloud/backup/import", {}, {}
        )

        assert response["status"] == 409
        body = json.loads(response["json"])
        assert body["code"] == "UNSUPPORTED_BACKUP_VERSION"
        assert body["details"] == {
            "remote_schema_revision": 96,
        }
        reporter.capture_exception.assert_not_called()

    @pytest.mark.asyncio
    async def test_migration_ahead_of_time_returns_503_unsupported_backup_version(
        self, mobile_router
    ):
        reporter = Mock()
        mobile_router.error_reporter = reporter

        async def route(_request):
            raise MigrationAheadOfTime(
                "Database has migrations not present in this version: v99.0.0:0_future"
            )

        mobile_router.add("POST", "/api/v1/cloud/backup/import", route)
        response = await mobile_router.handle(
            "POST", "/api/v1/cloud/backup/import", {}, {}
        )

        assert response["status"] == 503
        body = json.loads(response["json"])
        assert body["code"] == "UNSUPPORTED_BACKUP_VERSION"
        assert "v99.0.0:0_future" in body["message"]
        reporter.capture_exception.assert_not_called()

    @pytest.mark.asyncio
    async def test_unsupported_backup_protocol_returns_409(self, mobile_router):
        reporter = Mock()
        mobile_router.error_reporter = reporter

        async def route(_request):
            raise UnsupportedBackupProtocol(99)

        mobile_router.add("POST", "/api/v1/cloud/backup/import", route)
        response = await mobile_router.handle(
            "POST", "/api/v1/cloud/backup/import", {}, {}
        )

        assert response["status"] == 409
        body = json.loads(response["json"])
        assert body["code"] == "UNSUPPORTED_BACKUP_PROTOCOL"
        reporter.capture_exception.assert_not_called()
