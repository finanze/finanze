from unittest.mock import MagicMock

from application.ports.error_reporter_port import ErrorReporterPort
from domain.data_init import DataEncryptedError
from domain.exception.exceptions import (
    FlowNotFound,
    MissingFieldsError,
    ProtectedLabel,
)

from infrastructure.mcp.errors import LOCKED_MESSAGE, map_error


class TestMapError:
    def test_locked(self):
        assert str(map_error("tool", DataEncryptedError())) == LOCKED_MESSAGE

    def test_not_found(self):
        assert str(map_error("tool", FlowNotFound())) == "Flow not found"
        assert (
            str(map_error("tool", FlowNotFound("Flow X does not exist")))
            == "Flow not found: Flow X does not exist"
        )

    def test_invalid_input(self):
        assert (
            str(map_error("tool", ValueError("bad date"))) == "Invalid input: bad date"
        )
        assert str(map_error("tool", MissingFieldsError(["name"]))).startswith(
            "Invalid input"
        )

    def test_protected_label(self):
        assert "protected" in str(map_error("tool", ProtectedLabel()))

    def test_unexpected_errors_are_reported_and_hidden(self):
        reporter = MagicMock(spec=ErrorReporterPort)
        error = RuntimeError("db path /secret/file")

        mapped = map_error("get_positions", error, reporter)

        assert "/secret" not in str(mapped)
        assert str(mapped).startswith("Unexpected error")
        reporter.capture_exception.assert_called_once_with(
            error, tags={"mcp_tool": "get_positions"}
        )
