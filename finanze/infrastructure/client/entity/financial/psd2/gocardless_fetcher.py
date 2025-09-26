import logging
from typing import Tuple
from uuid import uuid4

from application.ports.external_entity_fetcher import (
    ExternalEntityFetcher,
)
from domain.dezimal import Dezimal
from domain.entity import EntityType
from domain.exception.exceptions import (
    ExternalEntityFailed,
    ExternalEntityLinkError,
    ExternalEntityLinkExpired,
    ExternalEntityNotFound,
    ExternalIntegrationRequired,
    TooManyRequests,
)
from domain.external_entity import (
    ExternalEntityConnectionResult,
    ExternalEntityFetchRequest,
    ExternalEntityLoginRequest,
    ExternalEntityProviderIntegrations,
    ExternalEntitySetupResponseCode,
    ProviderExternalEntityDetails,
)
from domain.external_integration import (
    ExternalIntegrationId,
)
from domain.global_position import (
    Account,
    Accounts,
    AccountType,
    GlobalPosition,
    ProductType,
)
from infrastructure.client.financial.gocardless.gocardless_client import (
    GoCardlessClient,
)
from requests.models import HTTPError


class GoCardlessFetcher(ExternalEntityFetcher):
    def __init__(self, client: GoCardlessClient):
        self._client = client
        self._log = logging.getLogger(__name__)

    def setup(self, integration_data: ExternalEntityProviderIntegrations):
        if not integration_data or not integration_data.gocardless:
            raise ExternalIntegrationRequired([ExternalIntegrationId.GOCARDLESS])

        client_credentials = integration_data.gocardless
        self._client.setup(client_credentials)

    async def create_or_link(
        self, request: ExternalEntityLoginRequest
    ) -> ExternalEntityConnectionResult:
        link, requisition_id, requisition_details = None, None, None
        institution_id = request.institution_id
        deleted_old_requisition = False
        create_new_requisition = False

        if request.external_entity and request.external_entity.provider_instance_id:
            requisition_id = request.external_entity.provider_instance_id
            requisition_details = self._client.get_requisition(requisition_id)
            institution_id = requisition_details["institution_id"]

            status = requisition_details["status"]
            if status == "LN":
                if request.relink:
                    self._client.delete_requisition(requisition_id)
                    deleted_old_requisition = True
                    create_new_requisition = True

                else:
                    return ExternalEntityConnectionResult(
                        ExternalEntitySetupResponseCode.ALREADY_LINKED
                    )

            elif status == "EX":
                self._client.delete_requisition(requisition_id)
                deleted_old_requisition = True
                create_new_requisition = True

            else:
                link = requisition_details["link"]

        elif institution_id:
            create_new_requisition = True

        else:
            raise ValueError(
                "Either institution_id or external_entity must be provided"
            )

        if create_new_requisition:
            try:
                link, requisition_id = self._init_session(request, institution_id)
            except Exception as e:
                # We have deleted a requisition, so we have to delete the orphan external entity that was linked to it
                raise ExternalEntityLinkError(deleted_old_requisition) from e

        try:
            requisition_details = self._client.get_requisition(requisition_id)
            agreement_details = self._client.get_agreement(
                requisition_details["agreement"]
            )  # type: ignore[index]
            requisition_details["agreement"] = agreement_details
        except Exception as ignored:
            self._log.error(
                f"Failed to fetch requisition and agreement details: {ignored}"
            )

        return ExternalEntityConnectionResult(
            ExternalEntitySetupResponseCode.CONTINUE_WITH_LINK,
            link,
            requisition_id,
            requisition_details,
        )

    def _init_session(
        self, request: ExternalEntityLoginRequest, institution_id: str
    ) -> Tuple[str, str]:
        institution_details = self._client.get_institution(institution_id)
        language = request.user_language or "EN"
        session = self._client.initialize_session(
            institution_id,
            str(request.external_entity.id),
            institution_details["transaction_total_days"],
            institution_details["max_access_valid_for_days"],
            base_redirect_url=request.redirect_host,
            user_language=language,
        )
        return session.link, session.requisition_id

    async def unlink(self, provider_instance_id: str):
        try:
            self._client.delete_requisition(provider_instance_id)
        except HTTPError as e:
            if e.response.status_code == 404:
                raise ExternalEntityNotFound() from e
            raise

    async def is_linked(self, provider_instance_id: str) -> bool:
        requisition_details = self._client.get_requisition(provider_instance_id)
        return requisition_details["status"] == "LN"

    async def get_entity(
        self, provider_entity_id: str
    ) -> ProviderExternalEntityDetails:
        details = self._client.get_institution(provider_entity_id)
        return ProviderExternalEntityDetails(
            id=details["id"],
            name=details["name"],
            bic=details.get("bic"),
            type=EntityType.FINANCIAL_INSTITUTION,
            icon=details.get("logo"),
        )

    async def get_entities(self, **kwargs) -> list[ProviderExternalEntityDetails]:
        country = kwargs.get("country")
        institutions = self._client.list_institutions(country)
        return [
            ProviderExternalEntityDetails(
                id=inst["id"],
                name=inst["name"],
                bic=inst.get("bic"),
                type=EntityType.FINANCIAL_INSTITUTION,
                icon=inst.get("logo"),
            )
            for inst in institutions
        ]

    async def global_position(
        self, request: ExternalEntityFetchRequest
    ) -> GlobalPosition:
        requisition_id = request.external_entity.provider_instance_id
        requisition_details = self._client.get_requisition(requisition_id)
        raw_accounts = requisition_details["accounts"]

        accounts: list[Account] = []

        for account_id in raw_accounts:
            try:
                balances = self._client.get_account_balances(account_id)
                details = self._client.get_account_details(account_id)
            except HTTPError as e:
                code = e.response.status_code
                if code in (401, 403, 409):
                    raise ExternalEntityLinkExpired() from e
                elif code == 429:
                    raise TooManyRequests() from e
                else:
                    raise ExternalEntityFailed() from e

            account_info = details.get("account", {})
            enabled = account_info.get("status") != "deleted"
            if not enabled:
                continue
            iban = account_info.get("iban")
            base_currency = account_info.get("currency")
            name = account_info.get("name") or account_info.get("displayName")
            cat = (account_info.get("cashAccountType") or "CACC").upper()
            type_map = {
                "CACC": AccountType.CHECKING,
                "SVGS": AccountType.SAVINGS,
                "CASH": AccountType.CHECKING,
                "ONDP": AccountType.CHECKING,
                "MGLD": AccountType.CHECKING,
                "MOMA": AccountType.CHECKING,
                "TRAS": AccountType.BROKERAGE,
            }
            acc_type = type_map.get(cat, AccountType.CHECKING)

            currency = None
            total_amount = Dezimal("0")
            balance = None

            self._log.info(balances)

            for b in balances.get("balances", []):
                btype = b.get("balanceType")
                if btype == "forwardAvailable":
                    continue

                balance = b.get("balanceAmount", {})
                total_amount = balance.get("amount")
                currency = balance.get("currency")

            if not balance:
                self._log.error("Account doesn't have balance details", extra=details)
                continue

            currency = currency or base_currency
            if not currency:
                self._log.error("Account without currency", extra=details)
                continue

            account = Account(
                id=uuid4(),
                total=total_amount,
                currency=currency,
                type=acc_type,
                name=name,
                iban=iban,
            )
            accounts.append(account)

        products = {ProductType.ACCOUNT: Accounts(accounts)}

        return GlobalPosition(id=uuid4(), entity=request.entity, products=products)
