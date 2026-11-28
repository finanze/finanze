import asyncio
from types import SimpleNamespace

import pytest
from infrastructure.client.ai.github_copilot.copilot_runtime_types import (
    CopilotErrorKind,
    classify_copilot_error,
)


class ProcessExitedError(Exception):
    pass


class JsonRpcError(Exception):
    def __init__(self, message: str, data=None):
        super().__init__(message)
        self.data = data


def _session_error(**kwargs):
    defaults = {
        "error_type": None,
        "error_code": None,
        "message": None,
        "status_code": None,
        "remediation": None,
    }
    return SimpleNamespace(**{**defaults, **kwargs})


@pytest.mark.parametrize(
    "error, session_error, kind",
    [
        (TimeoutError("timeout"), None, CopilotErrorKind.UNAVAILABLE),
        (asyncio.TimeoutError(), None, CopilotErrorKind.UNAVAILABLE),
        (ProcessExitedError("exit 1"), None, CopilotErrorKind.RUNTIME),
        (BrokenPipeError(), None, CopilotErrorKind.RUNTIME),
        (
            RuntimeError("failed"),
            _session_error(remediation=SimpleNamespace(value="sign_in")),
            CopilotErrorKind.AUTH,
        ),
        (JsonRpcError("Bad credentials"), None, CopilotErrorKind.AUTH),
        (
            JsonRpcError("failed", {"statusCode": 401}),
            None,
            CopilotErrorKind.AUTH,
        ),
        (
            RuntimeError("failed"),
            _session_error(status_code=429),
            CopilotErrorKind.RATE_LIMIT,
        ),
        (
            RuntimeError("failed"),
            _session_error(message="You have exceeded your premium request quota"),
            CopilotErrorKind.QUOTA,
        ),
        (
            RuntimeError("failed"),
            _session_error(message="Your AI credits for this month are used up"),
            CopilotErrorKind.QUOTA,
        ),
        (JsonRpcError("Model gpt-x is not available"), None, CopilotErrorKind.MODEL),
        (
            JsonRpcError("failed", {"status": "404"}),
            None,
            CopilotErrorKind.MODEL,
        ),
        (
            RuntimeError("failed"),
            _session_error(remediation="switch_account"),
            CopilotErrorKind.FORBIDDEN,
        ),
        (
            RuntimeError("failed"),
            _session_error(status_code=403),
            CopilotErrorKind.FORBIDDEN,
        ),
        (
            RuntimeError("Run completed without a structured assistant response"),
            None,
            CopilotErrorKind.SCHEMA,
        ),
        (RuntimeError("something odd"), None, CopilotErrorKind.UNAVAILABLE),
    ],
)
def test_classifies_copilot_errors(error, session_error, kind):
    assert classify_copilot_error(error, session_error) == kind
