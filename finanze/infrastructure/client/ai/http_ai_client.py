import asyncio
import logging
from typing import Optional

from application.ports.ai_client import AIClient
from domain.ai import AIReasoningEffort
from domain.exception.exceptions import (
    AIProviderError,
    AIProviderErrorCode,
    TooManyRequests,
)
from domain.external_integration import ExternalIntegrationPayload
from infrastructure.client.http.http_response import HttpResponse
from infrastructure.client.http.http_session import get_http_session

REASONING_EFFORTS = {
    AIReasoningEffort.NONE: "none",
    AIReasoningEffort.LOW: "low",
    AIReasoningEffort.MEDIUM: "medium",
    AIReasoningEffort.HIGH: "high",
    AIReasoningEffort.EXTRA_HIGH: "xhigh",
}


class HttpAIClient(AIClient):
    PROVIDER_NAME = "AI provider"
    BASE_URL = ""
    REQUEST_TIMEOUT_SECONDS = 90.0
    MAX_RETRIES = 3
    BACKOFF_SECONDS = 1.0
    RETRYABLE_STATUSES: tuple[int, ...] = (429, 500, 502, 503)

    def __init__(self):
        self._log = logging.getLogger(type(self).__module__)
        self._session = get_http_session()

    @staticmethod
    def _api_key(credentials: Optional[ExternalIntegrationPayload]) -> Optional[str]:
        return credentials.get("api_key") if credentials else None

    def _headers(self, credentials: Optional[ExternalIntegrationPayload]) -> dict:
        headers = {}
        api_key = self._api_key(credentials)
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    async def _should_retry(self, response: HttpResponse) -> bool:
        return response.status in self.RETRYABLE_STATUSES

    async def _request(
        self,
        method: str,
        path: str,
        credentials: Optional[ExternalIntegrationPayload],
        **kwargs,
    ) -> HttpResponse:
        attempt = 0
        while True:
            response = await self._session.request(
                method,
                f"{self.BASE_URL}{path}",
                headers=self._headers(credentials),
                timeout=self.REQUEST_TIMEOUT_SECONDS,
                **kwargs,
            )
            if attempt >= self.MAX_RETRIES or not await self._should_retry(response):
                return response
            attempt += 1
            await asyncio.sleep(self.BACKOFF_SECONDS * (2 ** (attempt - 1)))

    async def _send(
        self,
        method: str,
        path: str,
        credentials: Optional[ExternalIntegrationPayload],
        **kwargs,
    ) -> dict:
        response = await self._request(method, path, credentials, **kwargs)
        await self._check(response)
        return await response.json()

    async def _check(self, response: HttpResponse):
        if response.ok:
            return
        self._log.warning(
            f"{self.PROVIDER_NAME} request failed with status {response.status}: {await self._error_message(response)}"
        )
        error = await self._provider_error(response)
        if error is not None:
            raise error
        if response.status in (401, 403):
            raise AIProviderError(
                AIProviderErrorCode.INVALID_CREDENTIALS,
                f"Invalid {self.PROVIDER_NAME} credentials",
            )
        if response.status == 429:
            raise TooManyRequests()
        raise AIProviderError(
            AIProviderErrorCode.UNAVAILABLE,
            f"{self.PROVIDER_NAME} request failed ({response.status})",
        )

    async def _provider_error(self, response: HttpResponse) -> Optional[Exception]:
        return None

    @staticmethod
    async def _error_body(response: HttpResponse) -> dict:
        try:
            body = await response.json()
        except Exception:
            return {}
        error = body.get("error") if isinstance(body, dict) else None
        return error if isinstance(error, dict) else {}

    async def _error_message(self, response: HttpResponse) -> Optional[str]:
        return (await self._error_body(response)).get("message")
