import logging
from datetime import date, datetime
from uuid import uuid4

from application.ports.financial_entity_fetcher import FinancialEntityFetcher
from dateutil.tz import tzlocal
from domain.dezimal import Dezimal
from domain.entity_login import EntityLoginParams, EntityLoginResult
from domain.global_position import (
    Account,
    Accounts,
    AccountType,
    Card,
    Cards,
    CardType,
    CreditDetail,
    Credits,
    GlobalPosition,
    InterestType,
    Loan,
    Loans,
    LoanType,
    ProductType,
)
from domain.native_entities import CAJAMAR
from infrastructure.client.entity.financial.cajamar.cajamar_client import CajamarClient

_FIDIS_TYPE = "CR"
_CONFIRMING_TYPE = "CF"
_LEASING_TYPES = {"LS", "LL"}


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
    def _safe_parse_date(date_str: str | None) -> date | None:
        if not date_str:
            return None
        if isinstance(date_str, date) and not isinstance(date_str, datetime):
            return date_str
        raw = str(date_str).strip()
        if not raw:
            return None
        if "T" in raw:
            raw = raw.split("T", 1)[0]
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(raw, fmt).date()
            except ValueError:
                continue
        return None

    @staticmethod
    def _required_date(date_str: str | None) -> date:
        parsed = CajamarFetcher._safe_parse_date(date_str)
        if parsed:
            return parsed
        return datetime.now(tzlocal()).date()

    @staticmethod
    def _parse_money(value) -> Dezimal | None:
        if value is None:
            return None
        if isinstance(value, Dezimal):
            return value
        if isinstance(value, (int, float)):
            return Dezimal(value)
        raw = str(value).strip()
        if not raw or raw in {"—", "-"}:
            return None
        raw = raw.replace("€", "").replace("EUR", "").replace("%", "")
        raw = raw.replace("\xa0", " ").replace(" ", "")
        if "," in raw and "." in raw:
            if raw.rfind(",") > raw.rfind("."):
                raw = raw.replace(".", "").replace(",", ".")
            else:
                raw = raw.replace(",", "")
        elif "," in raw:
            raw = raw.replace(",", ".")
        try:
            return Dezimal(raw)
        except Exception:
            return None

    @staticmethod
    def _parse_interest(interest_raw) -> Dezimal:
        parsed = CajamarFetcher._parse_money(interest_raw)
        if parsed is None:
            return Dezimal(0)
        return round(parsed / 100, 6)

    def _loan_from_fields(
        self,
        *,
        description: str,
        currency: str | None,
        current_installment,
        amount_granted,
        pending_amount,
        creation_raw,
        maturity_raw,
        next_payment_raw,
        interest_raw,
        amortization_type: str | None = None,
    ) -> Loan | None:
        granted = self._parse_money(amount_granted)
        pending = self._parse_money(pending_amount)
        if granted is None or pending is None:
            return None

        installment = self._parse_money(current_installment) or Dezimal(0)
        is_mortgage = "HIPOTECA" in (description or "").upper()
        amortization = (amortization_type or "").upper()
        if "CONSTANTE" in amortization:
            interest_type = InterestType.FIXED
        else:
            interest_type = InterestType.VARIABLE

        return Loan(
            id=uuid4(),
            type=LoanType.MORTGAGE if is_mortgage else LoanType.STANDARD,
            currency=currency or "EUR",
            current_installment=round(installment, 2),
            interest_rate=self._parse_interest(interest_raw),
            loan_amount=round(granted, 2),
            creation=self._required_date(creation_raw),
            maturity=self._required_date(maturity_raw),
            principal_outstanding=round(pending, 2),
            next_payment_date=self._safe_parse_date(next_payment_raw),
            name=(description or "").strip() or None,
            interest_type=interest_type,
        )

    async def _map_standard_loan(self, financing_entry: dict) -> Loan | None:
        product_id = financing_entry.get("productId")
        if not product_id:
            return None

        origin = financing_entry.get("origin")
        try:
            loan_details = await self._client.get_loan(product_id, origin=origin) or {}
        except Exception as e:
            self._log.warning(f"Error fetching Cajamar loan details {product_id}: {e}")
            return None
        if not loan_details:
            return None

        description = (
            loan_details.get("description") or financing_entry.get("description") or ""
        )
        return self._loan_from_fields(
            description=description,
            currency=loan_details.get("currency") or financing_entry.get("currency"),
            current_installment=loan_details.get("amortizationQuotaAmount"),
            amount_granted=loan_details.get("amountGranted")
            or financing_entry.get("amountGranted"),
            pending_amount=loan_details.get("pendingAmount")
            or financing_entry.get("pendingAmount"),
            creation_raw=loan_details.get("agreementDate"),
            maturity_raw=loan_details.get("maturiryDate"),
            next_payment_raw=loan_details.get("nextAmortizationDate")
            or loan_details.get("nextSetlementDate"),
            interest_raw=loan_details.get("interest"),
            amortization_type=loan_details.get("amortizationType"),
        )

    async def _map_leasing(self, financing_entry: dict) -> Loan | None:
        product_id = financing_entry.get("productId")
        if not product_id:
            return None

        try:
            details = (
                await self._client.get_leasing(
                    product_id, association=financing_entry.get("association")
                )
                or {}
            )
        except Exception as e:
            self._log.warning(
                f"Error fetching Cajamar leasing details {product_id}: {e}"
            )
            details = {}
        description = (
            details.get("description") or financing_entry.get("description") or ""
        )
        return self._loan_from_fields(
            description=description,
            currency=financing_entry.get("currency") or "EUR",
            current_installment=details.get("fee"),
            amount_granted=financing_entry.get("amountGranted"),
            pending_amount=details.get("outstandingCapital")
            or financing_entry.get("pendingAmount"),
            creation_raw=details.get("hiringDate"),
            maturity_raw=details.get("endDate"),
            next_payment_raw=details.get("nextAmortization")
            or details.get("nextLiquidation"),
            interest_raw=details.get("interest"),
        )

    def _map_confirming(self, financing_entry: dict, details: dict) -> Loan | None:
        description = (
            details.get("title") or financing_entry.get("description") or "Confirming"
        )
        return self._loan_from_fields(
            description=description,
            currency=financing_entry.get("currency") or "EUR",
            current_installment=0,
            amount_granted=financing_entry.get("amountGranted"),
            pending_amount=financing_entry.get("pendingAmount"),
            creation_raw=None,
            maturity_raw=None,
            next_payment_raw=None,
            interest_raw=None,
        )

    async def _map_fidis_credits(
        self, financing_entries: list[dict]
    ) -> list[CreditDetail]:
        if not financing_entries:
            return []

        intro = await self._client.get_fidis_intro() or {}
        line_credits = intro.get("lineCredits") or []
        optk = intro.get("optk")
        credits: list[CreditDetail] = []

        for entry in financing_entries:
            account = entry.get("account")
            matched = next(
                (
                    line
                    for line in line_credits
                    if account and line.get("operation") == account
                ),
                None,
            )
            details = {}
            if matched and matched.get("index") is not None and optk:
                try:
                    details = (
                        await self._client.get_fidis_details(matched["index"], optk)
                        or {}
                    )
                except Exception as e:
                    self._log.warning(
                        f"Error fetching Cajamar FIDIS details {entry}: {e}"
                    )

            credit_limit = self._parse_money(
                (matched or {}).get("creditLimit") or entry.get("amountGranted")
            )
            available = self._parse_money(
                details.get("creditLimitAvailable")
                or (matched or {}).get("availableImport")
            )
            if credit_limit is None:
                continue
            drawn = (
                credit_limit - available
                if available is not None
                else self._parse_money(entry.get("pendingAmount")) or Dezimal(0)
            )
            credits.append(
                CreditDetail(
                    id=uuid4(),
                    currency=entry.get("currency") or "EUR",
                    credit_limit=round(credit_limit, 2),
                    drawn_amount=round(drawn, 2),
                    interest_rate=self._parse_interest(
                        details.get("interest") or (matched or {}).get("interest")
                    ),
                    name=(
                        details.get("description") or entry.get("description") or None
                    ),
                    creation=self._safe_parse_date(
                        details.get("dateConfirm") or (matched or {}).get("dateConfirm")
                    ),
                )
            )

        return credits

    async def _build_financings(
        self, raw_position: dict
    ) -> tuple[list[Loan], list[CreditDetail]]:
        raw_financings = (raw_position or {}).get("financings") or []
        loans: list[Loan] = []
        fidis_entries: list[dict] = []

        for entry in raw_financings:
            financing_type = entry.get("type")
            try:
                if financing_type == _FIDIS_TYPE:
                    fidis_entries.append(entry)
                    continue
                if financing_type in _LEASING_TYPES:
                    loan_obj = await self._map_leasing(entry)
                elif financing_type == _CONFIRMING_TYPE:
                    product_id = entry.get("productId")
                    details = {}
                    if product_id:
                        try:
                            details = (
                                await self._client.get_confirming(product_id) or {}
                            )
                        except Exception as e:
                            self._log.warning(
                                f"Error fetching Cajamar confirming {product_id}: {e}"
                            )
                    loan_obj = self._map_confirming(entry, details)
                else:
                    loan_obj = await self._map_standard_loan(entry)
                if loan_obj:
                    loans.append(loan_obj)
            except Exception as e:
                self._log.warning(f"Error mapping Cajamar financing entry {entry}: {e}")
                continue

        credits: list[CreditDetail] = []
        if fidis_entries:
            try:
                credits = await self._map_fidis_credits(fidis_entries)
            except Exception as e:
                self._log.warning(f"Error mapping Cajamar FIDIS credits: {e}")

        return loans, credits

    async def global_position(self) -> GlobalPosition:
        raw_position = await self._client.get_position() or {}

        accounts, accounts_by_raw_id = self._build_accounts(raw_position)
        cards = self._build_cards(raw_position, accounts_by_raw_id)
        loans, credits = await self._build_financings(raw_position)

        products = {}
        if accounts:
            products[ProductType.ACCOUNT] = Accounts(accounts)
        if cards:
            products[ProductType.CARD] = Cards(cards)
        if loans:
            products[ProductType.LOAN] = Loans(loans)
        if credits:
            products[ProductType.CREDIT] = Credits(credits)

        return GlobalPosition(id=uuid4(), entity=CAJAMAR, products=products)
