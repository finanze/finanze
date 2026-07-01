import base64
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple
from uuid import uuid4

import httpx
from application.ports.external_entity_fetcher import (
    ExternalEntityFetcher,
)
from dateutil.tz import tzlocal
from domain.dezimal import Dezimal
from domain.entity import EntityType
from domain.exception.exceptions import (
    ExternalEntityFailed,
    ExternalEntityLinkError,
    ExternalEntityLinkExpired,
    ExternalEntityNotFound,
    ExternalIntegrationRequired,
    ProviderInstitutionNotFound,
    TooManyRequests,
)
from domain.external_entity import (
    ExternalEntityConnectionResult,
    ExternalEntityFetchRequest,
    ExternalEntityLinkCompletion,
    ExternalEntityLoginRequest,
    ExternalEntitySetupResponseCode,
    ProviderExternalEntityDetails,
)
from domain.external_integration import (
    EnabledExternalIntegrations,
    ExternalIntegrationId,
)
from domain.global_position import (
    Account,
    Accounts,
    AccountType,
    GlobalPosition,
    ProductType,
)
from infrastructure.client.financial.enablebanking.enablebanking_client import (
    EnableBankingClient,
)

MAX_CONSENT_VALIDITY_SECONDS = 90 * 24 * 60 * 60

ACCOUNT_TYPE_MAP = {
    "CACC": AccountType.CHECKING,
    "SVGS": AccountType.SAVINGS,
    "CASH": AccountType.CHECKING,
    "ONDP": AccountType.CHECKING,
    "MGLD": AccountType.CHECKING,
    "MOMA": AccountType.CHECKING,
    "TRAS": AccountType.BROKERAGE,
}

BALANCE_TYPE_PREFERENCE = ["CLAV", "ITAV", "CLBD", "XPCD", "OTHR"]


def _build_auth_state(external_entity_id: str, completion_url: Optional[str]) -> str:
    if not completion_url:
        return external_entity_id
    encoded = (
        base64.urlsafe_b64encode(completion_url.encode("utf-8"))
        .decode("ascii")
        .rstrip("=")
    )
    return f"{external_entity_id}~{encoded}"


class EnableBankingFetcher(ExternalEntityFetcher):
    def __init__(self, client: EnableBankingClient):
        self._client = client
        self._log = logging.getLogger(__name__)

    async def setup(self, integrations: EnabledExternalIntegrations):
        if not integrations or ExternalIntegrationId.ENABLE_BANKING not in integrations:
            raise ExternalIntegrationRequired([ExternalIntegrationId.ENABLE_BANKING])

        client_credentials = integrations[ExternalIntegrationId.ENABLE_BANKING]
        await self._client.setup(client_credentials)

    async def create_or_link(
        self, request: ExternalEntityLoginRequest
    ) -> ExternalEntityConnectionResult:
        external_entity = request.external_entity

        aspsp = await self._resolve_aspsp(request, external_entity)
        if not aspsp:
            raise ProviderInstitutionNotFound()

        if external_entity.provider_instance_id and not request.relink:
            try:
                if await self.is_linked(external_entity.provider_instance_id):
                    return ExternalEntityConnectionResult(
                        ExternalEntitySetupResponseCode.ALREADY_LINKED
                    )
            except Exception:
                pass

        valid_until = self._compute_valid_until(aspsp)
        auth = await self._client.start_auth(
            aspsp_name=aspsp["name"],
            aspsp_country=aspsp["country"],
            state=_build_auth_state(str(external_entity.id), request.completion_url),
            valid_until=valid_until,
        )

        authorization_id = auth.get("authorization_id")
        payload = {
            "aspsp": {"name": aspsp["name"], "country": aspsp["country"]},
            "authorization_id": authorization_id,
        }

        return ExternalEntityConnectionResult(
            ExternalEntitySetupResponseCode.CONTINUE_WITH_LINK,
            auth.get("url"),
            authorization_id,
            payload,
        )

    async def complete_link(
        self, external_entity, callback_payload: dict
    ) -> ExternalEntityLinkCompletion:
        code = callback_payload.get("code")
        if not code:
            raise ExternalEntityLinkError(details="Missing authorization code")

        try:
            session = await self._client.create_session(code)
        except httpx.HTTPStatusError as e:
            self._log.error(
                "Failed to create Enable Banking session: %s",
                e.response.status_code,
            )
            raise ExternalEntityLinkError(
                details="Failed to complete authorization"
            ) from e

        session_id = session.get("session_id")
        accounts = self._map_session_accounts(session.get("accounts", []))
        aspsp = session.get("aspsp") or (external_entity.payload or {}).get("aspsp")
        valid_until = (session.get("access") or {}).get("valid_until")

        payload = {
            "accounts": accounts,
            "aspsp": aspsp,
            "valid_until": valid_until,
        }

        return ExternalEntityLinkCompletion(
            linked=True,
            provider_instance_id=session_id,
            payload=payload,
        )

    async def unlink(self, provider_instance_id: str):
        try:
            await self._client.delete_session(provider_instance_id)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ExternalEntityNotFound() from e
            raise

    async def is_linked(self, provider_instance_id: str) -> bool:
        try:
            session = await self._client.get_session(provider_instance_id)
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (404, 410):
                return False
            raise
        return session.get("status") == "AUTHORIZED"

    async def get_entity(
        self, provider_entity_id: str
    ) -> Optional[ProviderExternalEntityDetails]:
        country, name = self._parse_institution_id(provider_entity_id)
        if not country or not name:
            return None

        aspsp = await self._find_aspsp(country, name)
        if not aspsp:
            return None

        return self._map_aspsp(aspsp, country)

    async def get_entities(self, **kwargs) -> list[ProviderExternalEntityDetails]:
        country = kwargs.get("country")
        aspsps = await self._client.get_aspsps(country)
        return [self._map_aspsp(aspsp, country) for aspsp in aspsps]

    async def global_position(
        self, request: ExternalEntityFetchRequest
    ) -> GlobalPosition:
        payload = request.external_entity.payload or {}
        raw_accounts = payload.get("accounts", [])

        accounts: list[Account] = []

        for raw_account in raw_accounts:
            uid = raw_account.get("uid")
            if not uid:
                continue

            try:
                balances = await self._client.get_account_balances(uid)
            except httpx.HTTPStatusError as e:
                code = e.response.status_code
                if code in (401, 403, 410):
                    raise ExternalEntityLinkExpired() from e
                elif code == 429:
                    raise TooManyRequests() from e
                else:
                    raise ExternalEntityFailed() from e

            balance = self._select_balance(balances.get("balances", []))
            if not balance:
                self._log.error("Account %s has no usable balance", uid)
                continue

            amount = balance.get("balance_amount", {})
            currency = amount.get("currency") or raw_account.get("currency")
            if not currency:
                self._log.error("Account %s without currency", uid)
                continue

            cat = (raw_account.get("cash_account_type") or "CACC").upper()
            acc_type = ACCOUNT_TYPE_MAP.get(cat, AccountType.CHECKING)

            account = Account(
                id=uuid4(),
                total=Dezimal(str(amount.get("amount", "0"))),
                currency=currency,
                type=acc_type,
                name=raw_account.get("name"),
                iban=raw_account.get("iban"),
            )
            accounts.append(account)

        products = {ProductType.ACCOUNT: Accounts(accounts)}

        return GlobalPosition(id=uuid4(), entity=request.entity, products=products)

    async def _resolve_aspsp(
        self, request: ExternalEntityLoginRequest, external_entity
    ) -> Optional[dict]:
        if request.institution_id:
            country, name = self._parse_institution_id(request.institution_id)
        elif external_entity.payload and external_entity.payload.get("aspsp"):
            stored = external_entity.payload["aspsp"]
            country, name = stored.get("country"), stored.get("name")
        else:
            raise ValueError(
                "Either institution_id or external_entity must be provided"
            )

        if not country or not name:
            return None

        aspsp = await self._find_aspsp(country, name)
        if aspsp:
            return aspsp
        return {"name": name, "country": country}

    async def _find_aspsp(self, country: str, name: str) -> Optional[dict]:
        aspsps = await self._client.get_aspsps(country)
        for aspsp in aspsps:
            if aspsp.get("name") == name:
                return aspsp
        return None

    def _compute_valid_until(self, aspsp: dict) -> str:
        maximum = aspsp.get("maximum_consent_validity")
        if isinstance(maximum, int) and maximum > 0:
            seconds = min(maximum, MAX_CONSENT_VALIDITY_SECONDS)
        else:
            seconds = MAX_CONSENT_VALIDITY_SECONDS
        valid_until = datetime.now(tzlocal()) + timedelta(seconds=seconds)
        return valid_until.isoformat()

    @staticmethod
    def _parse_institution_id(
        institution_id: str,
    ) -> Tuple[Optional[str], Optional[str]]:
        if ":" not in institution_id:
            return None, None
        country, name = institution_id.split(":", 1)
        return country, name

    @staticmethod
    def _map_aspsp(
        aspsp: dict, country: Optional[str]
    ) -> ProviderExternalEntityDetails:
        aspsp_country = aspsp.get("country") or country
        name = aspsp.get("name")
        return ProviderExternalEntityDetails(
            id=f"{aspsp_country}:{name}",
            name=name,
            bic=aspsp.get("bic") or "",
            type=EntityType.FINANCIAL_INSTITUTION,
            icon=aspsp.get("logo"),
        )

    @staticmethod
    def _map_session_accounts(raw_accounts: list[dict]) -> list[dict]:
        accounts = []
        for account in raw_accounts:
            account_id = account.get("account_id") or {}
            accounts.append(
                {
                    "uid": account.get("uid"),
                    "currency": account.get("currency"),
                    "name": account.get("name"),
                    "iban": account_id.get("iban"),
                    "cash_account_type": account.get("cash_account_type"),
                }
            )
        return accounts

    @staticmethod
    def _select_balance(balances: list[dict]) -> Optional[dict]:
        if not balances:
            return None
        by_type = {}
        for balance in balances:
            btype = balance.get("balance_type")
            if btype and btype not in by_type:
                by_type[btype] = balance
        for preferred in BALANCE_TYPE_PREFERENCE:
            if preferred in by_type:
                return by_type[preferred]
        return balances[0]
