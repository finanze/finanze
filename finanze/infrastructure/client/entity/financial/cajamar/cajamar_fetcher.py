import logging
from datetime import datetime
from uuid import uuid4

from application.ports.financial_entity_fetcher import FinancialEntityFetcher
from domain.dezimal import Dezimal
from domain.entity_login import EntityLoginParams, EntityLoginResult
from domain.global_position import (
    Account,
    Accounts,
    AccountType,
    Card,
    Cards,
    CardType,
    GlobalPosition,
    InterestType,
    Loan,
    Loans,
    LoanType,
    ProductType,
)
from domain.native_entities import CAJAMAR
from infrastructure.client.entity.financial.cajamar.cajamar_client import CajamarClient


class CajamarFetcher(FinancialEntityFetcher):
    def __init__(self):
        self._client = CajamarClient()
        self._log = logging.getLogger(__name__)

    async def login(self, login_params: EntityLoginParams) -> EntityLoginResult:
        credentials = login_params.credentials
        username, password = credentials["user"], credentials["password"]
        return await self._client.login(username, password, login_params.session)

    def _build_accounts(
        self, raw_position: dict
    ) -> tuple[list[Account], dict[str, Account]]:
        raw_accounts = (raw_position or {}).get("accounts") or []
        accounts: list[Account] = []
        accounts_by_raw_id: dict[str, Account] = {}

        for entry in raw_accounts:
            try:
                accounting_balance = Dezimal(entry.get("accountingBalance") or 0)
                available_balance = Dezimal(entry.get("availableBalance") or 0)
                retained = accounting_balance - available_balance
                iban_raw = entry.get("iban") or None
                iban = iban_raw.replace(" ", "") if isinstance(iban_raw, str) else None
                currency = entry.get("currency")
                account_obj = Account(
                    id=uuid4(),
                    total=round(available_balance, 2),
                    currency=currency,
                    type=AccountType.CHECKING,
                    iban=iban,
                    retained=round(retained, 2),
                )
                accounts.append(account_obj)
                raw_id = entry.get("id")
                if raw_id:
                    accounts_by_raw_id[raw_id] = account_obj
            except Exception as e:
                self._log.warning(f"Error mapping Cajamar account entry {entry}: {e}")
                continue

        return accounts, accounts_by_raw_id

    def _map_card(
        self, entry: dict, accounts_by_raw_id: dict[str, Account]
    ) -> Card | None:
        status = entry.get("status")
        active = status == "OPERATIVA"

        raw_type = entry.get("type")
        if raw_type == "DT":
            card_type = CardType.DEBIT
        elif raw_type == "CT" or raw_type == "MX":
            card_type = CardType.CREDIT
        else:
            self._log.warning(f"Unknown card type {raw_type}")
            return None

        name = entry.get("description") or None
        currency = entry.get("currency")
        limit_val = entry.get("limit")
        limit = Dezimal(limit_val) if limit_val is not None else None
        used_cred = entry.get("usedCred") if card_type == CardType.CREDIT else 0
        used = round(Dezimal(used_cred or 0), 2)
        pan = entry.get("pan") or ""
        ending = pan[-4:] if len(pan) >= 4 else None

        related_raw_account = entry.get("account")
        related_account = None
        if related_raw_account and related_raw_account in accounts_by_raw_id:
            related_account = accounts_by_raw_id[related_raw_account].id

        return Card(
            id=uuid4(),
            name=name,
            ending=ending,
            currency=currency,
            type=card_type,
            limit=limit,
            used=used,
            active=active,
            related_account=related_account,
        )

    def _build_cards(
        self, raw_position: dict, accounts_by_raw_id: dict[str, Account]
    ) -> list[Card]:
        raw_cards = (raw_position or {}).get("cards") or []
        cards: list[Card] = []
        for entry in raw_cards:
            try:
                card_obj = self._map_card(entry, accounts_by_raw_id)
                if card_obj:
                    cards.append(card_obj)
            except Exception as e:
                self._log.warning(f"Error mapping Cajamar card entry {entry}: {e}")
                continue
        return cards

    @staticmethod
    def _safe_parse_date(date_str: str | None) -> datetime.date:
        if not date_str:
            return datetime.now().date()
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except Exception:
            return datetime.now().date()

    @staticmethod
    def _parse_interest(interest_raw: str | None) -> Dezimal:
        if not interest_raw:
            return Dezimal(0)
        try:
            interest_clean = (
                interest_raw.replace("%", "").replace(" ", "").replace(",", ".")
            )
            return round(Dezimal(interest_clean) / 100, 6)
        except Exception:
            return Dezimal(0)

    async def _map_loan(self, financing_entry: dict) -> Loan | None:
        product_id = financing_entry.get("productId")
        if not product_id:
            return None

        loan_details = await self._client.get_loan(product_id) or {}
        if not loan_details:
            return None

        description = (
            loan_details.get("description") or financing_entry.get("description") or ""
        )
        is_mortgage = "HIPOTECA" in description.upper()
        loan_type = LoanType.MORTGAGE if is_mortgage else LoanType.STANDARD
        currency = loan_details.get("currency") or financing_entry.get("currency")
        current_installment = Dezimal(loan_details.get("amortizationQuotaAmount") or 0)
        amount_granted = Dezimal(
            loan_details.get("amountGranted") or financing_entry.get("amountGranted")
        )
        pending_amount = Dezimal(
            loan_details.get("pendingAmount") or financing_entry.get("pendingAmount")
        )
        creation_date = self._safe_parse_date(loan_details.get("agreementDate"))
        maturity_date = self._safe_parse_date(loan_details.get("maturiryDate"))

        next_payment_date = None
        next_payment_raw = loan_details.get("nextAmortizationDate") or loan_details.get(
            "nextSetlementDate"
        )

        if next_payment_raw:
            try:
                next_payment_date = datetime.strptime(
                    next_payment_raw, "%Y-%m-%d"
                ).date()
            except Exception:
                next_payment_date = None
        interest_rate = self._parse_interest(loan_details.get("interest"))

        amortization_type = (loan_details.get("amortizationType") or "").upper()
        if "CONSTANTE" in amortization_type:
            interest_type = InterestType.FIXED
        else:
            interest_type = InterestType.VARIABLE

        return Loan(
            id=uuid4(),
            type=loan_type,
            currency=currency,
            current_installment=round(current_installment, 2),
            interest_rate=interest_rate,
            loan_amount=round(amount_granted, 2),
            creation=creation_date,
            maturity=maturity_date,
            principal_outstanding=round(pending_amount, 2),
            next_payment_date=next_payment_date,
            name=description.strip() or None,
            interest_type=interest_type,
        )

    async def _build_loans(self, raw_position: dict) -> list[Loan]:
        raw_loans = (raw_position or {}).get("financings") or []
        loans: list[Loan] = []
        for entry in raw_loans:
            try:
                loan_obj = await self._map_loan(entry)
                if loan_obj:
                    loans.append(loan_obj)
            except Exception as e:
                self._log.warning(f"Error mapping Cajamar loan entry {entry}: {e}")
                continue
        return loans

    async def global_position(self) -> GlobalPosition:
        raw_position = await self._client.get_position() or {}

        accounts, accounts_by_raw_id = self._build_accounts(raw_position)
        cards = self._build_cards(raw_position, accounts_by_raw_id)
        loans = await self._build_loans(raw_position)

        products = {}
        if accounts:
            products[ProductType.ACCOUNT] = Accounts(accounts)
        if cards:
            products[ProductType.CARD] = Cards(cards)
        if loans:
            products[ProductType.LOAN] = Loans(loans)

        return GlobalPosition(id=uuid4(), entity=CAJAMAR, products=products)
