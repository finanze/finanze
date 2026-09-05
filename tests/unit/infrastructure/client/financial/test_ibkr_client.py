import base64
from datetime import date

import httpx
import pytest

from infrastructure.client.entity.financial.ibkr.ibkr_client import (
    IBKRClient,
    IBKRStatementError,
)

FROM_DATE = date(2025, 1, 1)
TO_DATE = date(2025, 12, 31)

CSV_STATEMENT = (
    "Statement,Header,Field Name,Field Value\r\n"
    "Statement,Data,BrokerName,Interactive Brokers\r\n"
)

AM_HTML = "<html><script>var AM_SESSION_ID = 'am-session-1';</script></html>"
ACCOUNT_ID = "U1234567"
ACCOUNT_HASH = -310551676
PAGE_INFO = {
    "picker": {
        "activeSelections": [
            {"id": 42, "accountId": "U7654321"},
            {"id": ACCOUNT_HASH, "accountId": ACCOUNT_ID},
        ]
    }
}


def _json_statement(csv_text: str = CSV_STATEMENT) -> dict:
    return {"fileContent": base64.b64encode(csv_text.encode("utf-8")).decode()}


class FakeIBKR:
    """Serves canned responses for the Account Management statement flow."""

    def __init__(
        self, run_responses: list[httpx.Response], page_info: dict | None = None
    ):
        self._run_responses = run_responses
        self._page_info = PAGE_INFO if page_info is None else page_info
        self.run_calls = 0
        self.am_auth_calls = 0
        self.run_headers: list[httpx.Headers] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/AmAuthentication"):
            self.am_auth_calls += 1
            return httpx.Response(200, text=AM_HTML)
        if path.endswith("/Statements/PageInfo"):
            return httpx.Response(200, json=self._page_info)
        if path.endswith("/Statements/Run"):
            self.run_headers.append(request.headers)
            resp = self._run_responses[
                min(self.run_calls, len(self._run_responses) - 1)
            ]
            self.run_calls += 1
            return resp
        raise AssertionError(f"Unexpected request to {path}")


def _client(fake: FakeIBKR) -> IBKRClient:
    client = IBKRClient()
    client._account_id = ACCOUNT_ID
    client._http = httpx.AsyncClient(
        transport=httpx.MockTransport(fake.handler),
        base_url="https://www.interactivebrokers.ie",
    )
    return client


@pytest.mark.asyncio
async def test_download_activity_statement_decodes_json_envelope():
    fake = FakeIBKR([httpx.Response(200, json=_json_statement())])

    result = await _client(fake).download_activity_statement(FROM_DATE, TO_DATE)

    assert result == CSV_STATEMENT
    assert fake.run_calls == 1


@pytest.mark.asyncio
async def test_download_activity_statement_retries_with_a_new_am_session():
    fake = FakeIBKR(
        [
            httpx.Response(200, text="", headers={"content-type": "text/html"}),
            httpx.Response(200, json=_json_statement()),
        ]
    )

    result = await _client(fake).download_activity_statement(FROM_DATE, TO_DATE)

    assert result == CSV_STATEMENT
    assert fake.run_calls == 2
    assert fake.am_auth_calls == 2


@pytest.mark.asyncio
async def test_download_activity_statement_raises_on_non_json_response():
    fake = FakeIBKR(
        [httpx.Response(200, text="", headers={"content-type": "text/html"})]
    )

    with pytest.raises(IBKRStatementError):
        await _client(fake).download_activity_statement(FROM_DATE, TO_DATE)

    assert fake.run_calls == 2


@pytest.mark.asyncio
async def test_download_activity_statement_raises_on_error_status():
    fake = FakeIBKR([httpx.Response(500, text="boom")])

    with pytest.raises(IBKRStatementError):
        await _client(fake).download_activity_statement(FROM_DATE, TO_DATE)


@pytest.mark.asyncio
async def test_download_activity_statement_returns_empty_without_file_content():
    fake = FakeIBKR([httpx.Response(200, json={"fileContent": ""})])

    result = await _client(fake).download_activity_statement(FROM_DATE, TO_DATE)

    assert result == ""


@pytest.mark.asyncio
async def test_statement_request_carries_the_picked_account_hash():
    fake = FakeIBKR([httpx.Response(200, json=_json_statement())])

    await _client(fake).download_activity_statement(FROM_DATE, TO_DATE)

    assert fake.run_headers[0]["AccountHash"] == str(ACCOUNT_HASH)


@pytest.mark.asyncio
async def test_statement_fails_when_the_picker_has_no_account():
    fake = FakeIBKR(
        [httpx.Response(200, json=_json_statement())],
        page_info={"picker": {"activeSelections": []}},
    )

    with pytest.raises(IBKRStatementError):
        await _client(fake).download_activity_statement(FROM_DATE, TO_DATE)

    assert fake.run_calls == 0


@pytest.mark.asyncio
async def test_period_without_statement_is_not_an_error():
    unavailable = {
        "errors": {
            "stmtError": "There is no statement available for the account(s) and date(s) selected."
        }
    }
    fake = FakeIBKR([httpx.Response(601, json=unavailable)])

    result = await _client(fake).download_activity_statement(FROM_DATE, TO_DATE)

    assert result == ""
    # IBKR gave a definitive answer, so there is nothing to retry
    assert fake.run_calls == 1
    assert fake.am_auth_calls == 1
