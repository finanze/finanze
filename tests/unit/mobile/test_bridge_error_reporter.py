import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType

from domain.telemetry import TelemetryLevel


_MODULE_PATH = (
    Path(__file__).resolve().parents[3]
    / "frontend/app/src/python/finanze/infrastructure/telemetry/bridge_error_reporter.py"
)


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
