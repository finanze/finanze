import logging
from typing import Optional

import requests
from application.ports.connectable_integration import ConnectableIntegration
from cachetools import TTLCache, cached
from domain.exception.exceptions import (
    AddressNotFound,
    IntegrationSetupError,
    IntegrationSetupErrorCode,
    TooManyRequests,
)
from domain.external_integration import (
    ExternalIntegrationPayload,
)
from infrastructure.client.http.backoff import http_get_with_backoff


class EthplorerClient(ConnectableIntegration):
    TTL = 60
    DEFAULT_API_KEY = "freekey"
    COOLDOWN = 0.4
    MAX_RETRIES = 3
    BACKOFF_FACTOR = 0.5

    def __init__(self):
        self._log = logging.getLogger(__name__)

    def setup(self, credentials: ExternalIntegrationPayload):
        url = f"https://api.ethplorer.io/getLastBlock?apiKey={self._get_api_key(credentials)}"
        self._fetch(url)

    @cached(cache=TTLCache(maxsize=50, ttl=TTL))
    def fetch_address_info(
        self,
        base_url: str,
        address: str,
        credentials: Optional[ExternalIntegrationPayload] = None,
    ) -> dict:
        url = f"{base_url}/getAddressInfo/{address}?apiKey={self._get_api_key(credentials)}"
        return self._fetch(url)

    def _get_api_key(
        self, credentials: Optional[ExternalIntegrationPayload] = None
    ) -> str:
        if credentials and "api_key" in credentials:
            return credentials["api_key"]
        return self.DEFAULT_API_KEY

    def _fetch(
        self,
        url: str,
    ) -> dict:
        try:
            response = http_get_with_backoff(
                url,
                cooldown=self.COOLDOWN,
                max_retries=self.MAX_RETRIES,
                backoff_factor=self.BACKOFF_FACTOR,
                log=self._log,
            )
        except requests.RequestException as e:
            self._log.error(f"Request error calling Ethplorer endpoint {url}: {e}")
            raise

        if not response.ok:
            if response.status_code == 401:
                raise IntegrationSetupError(
                    IntegrationSetupErrorCode.INVALID_CREDENTIALS
                )

            if response.status_code == 429:
                raise TooManyRequests()

            self._log.error(
                f"Error fetching from Ethplorer: {response.status_code} {response.text}"
            )
            response.raise_for_status()

        data = response.json()
        if "error" in data:
            error = data["error"]
            self._log.error(f"Ethplorer API error: {error}")
            if error.get("code") == 150:
                raise AddressNotFound()
            raise Exception(f"Ethplorer API error: {error.get('message')}")

        return data
