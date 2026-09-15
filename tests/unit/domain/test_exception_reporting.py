import asyncio

import pytest

from domain.data_init import DataEncryptedError
from domain.exception.exceptions import (
    EntityNotFound,
    NoAdapterFound,
    NoUserLogged,
    TooManyRequests,
)
from domain.exception.reporting import is_reportable


class TestIsReportable:
    @pytest.mark.parametrize(
        "exc",
        [
            EntityNotFound("entity"),
            NoUserLogged(),
            TooManyRequests(),
            DataEncryptedError(),
            ValueError("invalid"),
        ],
    )
    def test_expected_business_errors_are_not_reported(self, exc):
        assert not is_reportable(exc)

    @pytest.mark.parametrize(
        "exc",
        [asyncio.CancelledError(), KeyboardInterrupt(), SystemExit()],
    )
    def test_control_flow_errors_are_not_reported(self, exc):
        assert not is_reportable(exc)

    def test_network_errors_are_not_reported(self):
        assert not is_reportable(ConnectionError("offline"))
        assert not is_reportable(TimeoutError("timeout"))

    def test_third_party_network_errors_are_not_reported(self):
        import httpx

        assert not is_reportable(httpx.ConnectError("failed"))

    @pytest.mark.parametrize(
        "exc",
        [
            TypeError("unexpected"),
            KeyError("missing"),
            AttributeError("nope"),
            NoAdapterFound("no adapter"),
        ],
    )
    def test_unexpected_errors_are_reported(self, exc):
        assert is_reportable(exc)
