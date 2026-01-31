import logging
import time
from typing import List, Optional

from application.ports.connectable_integration import ConnectableIntegration
from cachetools import TTLCache, cached
from domain.exception.exceptions import IntegrationSetupError, IntegrationSetupErrorCode
from domain.external_integration import (
    ExternalIntegrationPayload,
)
from nordigen import NordigenClient
from nordigen.types import RequisitionDto
from nordigen.types.types import (
    AgreementsList,
    EnduserAgreement,
    Institutions,
    TokenType,
)
from requests.models import HTTPError


class GoCardlessClient(ConnectableIntegration):
    TOKEN_REFRESH_MARGIN_SECONDS = 30
    DEFAULT_BASE_REDIRECT_URL = "http://localhost"
    REDIRECT_PATH = "/api/v1/entities/external/complete"

    def __init__(self, port) -> None:
        self._log = logging.getLogger(__name__)
        self._client: Optional[NordigenClient] = None
        self._credentials: Optional[ExternalIntegrationPayload] = None
        self._refresh_token: Optional[str] = None
        self._access_expires_at: Optional[float] = None
        self._refresh_expires_at: Optional[float] = None

        self.DEFAULT_BASE_REDIRECT_URL = f"{self.DEFAULT_BASE_REDIRECT_URL}:{port}"

    async def setup(self, credentials: ExternalIntegrationPayload) -> None:
        self._credentials = credentials

        self._client = NordigenClient(
            secret_id=credentials["secret_id"], secret_key=credentials["secret_key"]
        )
        try:
            token = self._client.generate_token()
            self._update_token_state(token)
        except HTTPError as e:
            self._log.error(
                "Error generating GoCardless token: %s", getattr(e, "response", e)
            )
            if e.response is not None and e.response.status_code == 401:
                raise IntegrationSetupError(
                    IntegrationSetupErrorCode.INVALID_CREDENTIALS
                ) from e
            raise IntegrationSetupError(IntegrationSetupErrorCode.UNKNOWN) from e
        except Exception as e:
            self._log.exception("Unexpected error during GoCardless setup")
            raise IntegrationSetupError(IntegrationSetupErrorCode.UNKNOWN) from e

    def refresh_token(self, refresh_token: str) -> TokenType:
        client = self._ensure_client()
        token = client.exchange_token(refresh_token)
        self._update_token_state(token)
        return token

    @cached(cache=TTLCache(maxsize=100, ttl=86400))
    def list_institutions(self, country_code: str) -> List[Institutions]:
        client = self._ensure_client()
        return client.institution.get_institutions(country_code)

    @cached(cache=TTLCache(maxsize=100, ttl=86400))
    def get_institution(self, institution_id: str) -> dict:
        client = self._ensure_client()
        return client.institution.get_institution_by_id(institution_id)

    @cached(cache=TTLCache(maxsize=10, ttl=5))
    def list_agreements(self, limit: int = 100, offset: int = 0) -> AgreementsList:
        client = self._ensure_client()
        return client.agreement.get_agreements(limit=limit, offset=offset)

    @cached(cache=TTLCache(maxsize=10, ttl=60))
    def get_agreement(self, agreement_id: str) -> EnduserAgreement:
        client = self._ensure_client()
        return client.agreement.get_agreement_by_id(agreement_id)

    def delete_agreement(self, agreement_id: str) -> dict:
        client = self._ensure_client()
        return client.agreement.delete_agreement(agreement_id)

    def initialize_session(
        self,
        institution_id: str,
        reference_id: str,
        max_historical_days,
        access_valid_for_days,
        base_redirect_url: Optional[str] = None,
        user_language: str = "EN",
        account_selection: bool = False,
    ) -> RequisitionDto:
        client = self._ensure_client()

        agreement = client.agreement.create_agreement(
            max_historical_days=max_historical_days,
            access_valid_for_days=access_valid_for_days,
            institution_id=institution_id,
        )

        redirect_url_base = base_redirect_url or self.DEFAULT_BASE_REDIRECT_URL
        if not redirect_url_base.startswith("http"):
            redirect_url_base = f"http://{redirect_url_base}"
        if redirect_url_base.endswith("/"):
            redirect_url_base = redirect_url_base[:-1]
        redirect_uri = f"{redirect_url_base}{self.REDIRECT_PATH}"

        requisition_dict = {
            "redirect_uri": redirect_uri,
            "reference_id": reference_id,
            "institution_id": institution_id,
            "agreement": agreement["id"],
            "user_language": user_language,
            "account_selection": account_selection,
        }

        requisition = client.requisition.create_requisition(**requisition_dict)

        return RequisitionDto(
            link=requisition["link"], requisition_id=requisition["id"]
        )

    @cached(cache=TTLCache(maxsize=10, ttl=5))
    def get_requisitions(self, limit: int = 100, offset: int = 0) -> dict:
        client = self._ensure_client()
        return client.requisition.get_requisitions(limit=limit, offset=offset)

    def get_requisition(self, requisition_id: str) -> dict:
        client = self._ensure_client()
        return client.requisition.get_requisition_by_id(requisition_id)

    def delete_requisition(self, requisition_id: str) -> dict:
        client = self._ensure_client()
        return client.requisition.delete_requisition(requisition_id)

    def _account_api(self, account_id: str):
        client = self._ensure_client()
        return client.account_api(id=account_id)

    @cached(cache=TTLCache(maxsize=100, ttl=10))
    def get_account_balances(self, account_id: str) -> dict:
        return self._account_api(account_id).get_balances()

    @cached(cache=TTLCache(maxsize=100, ttl=3600))
    def get_account_metadata(self, account_id: str) -> dict:
        return self._account_api(account_id).get_metadata()

    @cached(cache=TTLCache(maxsize=100, ttl=3600))
    def get_account_details(self, account_id: str) -> dict:
        return self._account_api(account_id).get_details()

    @cached(cache=TTLCache(maxsize=100, ttl=30))
    def get_account_transactions(
        self,
        account_id: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> dict:
        params: dict = {}
        if date_from:
            params["date_from"] = date_from
        if date_to:
            params["date_to"] = date_to
        return self._account_api(account_id).get_transactions(**params)

    def _ensure_client(self) -> NordigenClient:
        if not self._client or not self._credentials:
            raise ValueError("Client not set up. Call setup() first.")

        if self._access_token_needs_refresh():
            if self._refresh_token_valid():
                self._attempt_token_refresh()
            else:
                self._regenerate_token()
        return self._client

    def _update_token_state(self, token: TokenType) -> None:
        now = time.time()
        access_ttl = token.get("access_expires")
        refresh_ttl = token.get("refresh_expires")
        if isinstance(access_ttl, int):
            self._access_expires_at = now + access_ttl
        if isinstance(refresh_ttl, int):
            self._refresh_expires_at = now + refresh_ttl
        self._refresh_token = token.get("refresh")

    def _access_token_needs_refresh(self) -> bool:
        if self._access_expires_at is None:
            return True
        return (
            self._access_expires_at - time.time()
        ) <= self.TOKEN_REFRESH_MARGIN_SECONDS

    def _refresh_token_valid(self) -> bool:
        if self._refresh_expires_at is None:
            return False
        return (
            time.time() < self._refresh_expires_at - self.TOKEN_REFRESH_MARGIN_SECONDS
        )

    def _attempt_token_refresh(self) -> None:
        if not self._client or not self._refresh_token:
            return
        try:
            token = self._client.exchange_token(self._refresh_token)
            self._update_token_state(token)
        except HTTPError:
            self._regenerate_token()
        except Exception:
            self._regenerate_token()

    def _regenerate_token(self) -> None:
        if not self._client or not self._credentials:
            raise ValueError("Cannot regenerate token without client and credentials")
        token = self._client.generate_token()
        self._update_token_state(token)
