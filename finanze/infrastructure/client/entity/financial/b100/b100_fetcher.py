import logging
import re
from datetime import datetime
from typing import Optional
from uuid import uuid4

from application.ports.financial_entity_fetcher import FinancialEntityFetcher
from dateutil.tz import tzlocal
from domain.constants import CAPITAL_GAINS_BASE_TAX
from domain.dezimal import Dezimal
from domain.entity_login import EntityLoginParams, EntityLoginResult
from domain.fetch_record import DataSource
from domain.fetch_result import FetchOptions
from domain.global_position import (
    Account,
    Accounts,
    AccountType,
    Card,
    Cards,
    CardType,
    GlobalPosition,
    ProductType,
)
from domain.native_entities import B100
from domain.transactions import AccountTx, Transactions, TxType
from infrastructure.client.entity.financial.b100.b100_client import B100Client

ACCOUNT_TYPE_MAP = {
    "CHECKING": AccountType.CHECKING,
    "SAVING": AccountType.SAVINGS,
    "HEALTH_SAVING": AccountType.SAVINGS,
}

ACCOUNT_NAME_MAP = {
    "CHECKING": "Cuenta",
    "SAVING": "Cuenta Ahorro",
    "HEALTH_SAVING": "Cuenta Health",
}

TAE_PATTERN = re.compile(r"(\d+,\d+)\s*%\s*TAE")

MOVEMENTS_PAGE_SIZE = 50


class B100Fetcher(FinancialEntityFetcher):
    def __init__(self):
        self._client = B100Client()
        self._log = logging.getLogger(__name__)

    async def login(self, login_params: EntityLoginParams) -> EntityLoginResult:
        credentials = login_params.credentials
        user, pin = credentials["user"], credentials["password"]
        otp = login_params.two_factor.code if login_params.two_factor else None
        return await self._client.login(
            user, pin, login_params.session, otp, login_params.keychain
        )

    @staticmethod
    def _parse_tae(tiers: list) -> Optional[Dezimal]:
        matches = []
        for tier in tiers or []:
            description = tier.get("description") or ""
            matches.extend(TAE_PATTERN.findall(description))
        if not matches:
            return None
        return round(Dezimal(matches[-1].replace(",", ".")) / 100, 6)

    @staticmethod
    def _bban(iban: Optional[str]) -> Optional[str]:
        if not iban:
            return None
        return iban[4:]

    async def _build_accounts(
        self,
    ) -> tuple[list[Account], dict[str, Account], dict[str, Account]]:
        raw_accounts = await self._client.get_accounts() or []
        accounts: list[Account] = []
        accounts_by_raw_id: dict[str, Account] = {}
        accounts_by_bban: dict[str, Account] = {}

        for entry in raw_accounts:
            raw_id = entry.get("id")
            account_type_raw = entry.get("accountType")
            total_amount = entry.get("totalAmount") or {}
            hold_amount = entry.get("holdAmount") or {}
            iban = entry.get("iban")

            interest = None
            try:
                detail = await self._client.get_account(raw_id)
                interest = self._parse_tae(detail.get("remunerationTiers"))
            except Exception as e:
                self._log.warning(f"Error fetching B100 account detail {raw_id}: {e}")

            account = Account(
                id=uuid4(),
                total=round(Dezimal(total_amount.get("quantity") or 0), 2),
                currency=total_amount.get("currency"),
                type=ACCOUNT_TYPE_MAP.get(account_type_raw, AccountType.CHECKING),
                name=ACCOUNT_NAME_MAP.get(account_type_raw),
                iban=iban,
                interest=interest,
                retained=round(Dezimal(hold_amount.get("quantity") or 0), 2),
            )
            accounts.append(account)
            if raw_id:
                accounts_by_raw_id[raw_id] = account
            bban = self._bban(iban)
            if bban:
                accounts_by_bban[bban] = account

        return accounts, accounts_by_raw_id, accounts_by_bban

    async def _build_cards(self, accounts_by_bban: dict[str, Account]) -> list[Card]:
        raw_cards = await self._client.get_cards() or []
        cards: list[Card] = []

        for entry in raw_cards:
            raw_id = entry.get("id")
            card_type = (
                CardType.CREDIT if entry.get("cardType") == "CREDIT" else CardType.DEBIT
            )
            credit_limit = entry.get("creditLimit") or {}
            drawn_amount = entry.get("drawnAmount") or {}
            available_amount = entry.get("availableAmount") or {}
            currency = (
                credit_limit.get("currency")
                or drawn_amount.get("currency")
                or available_amount.get("currency")
            )
            pan = entry.get("pan") or ""
            ending = pan[-4:] if len(pan) >= 4 else None
            active = entry.get("status") == "ACTIVE" and not entry.get("suspended")

            related_account = None
            try:
                detail = await self._client.get_card(raw_id)
                account_number = (detail.get("account") or {}).get("number")
                if account_number:
                    bban = account_number.replace("-", "")
                    matched = accounts_by_bban.get(bban)
                    if matched:
                        related_account = matched.id
            except Exception as e:
                self._log.warning(f"Error fetching B100 card detail {raw_id}: {e}")

            cards.append(
                Card(
                    id=uuid4(),
                    name=entry.get("alias"),
                    ending=ending,
                    currency=currency,
                    type=card_type,
                    limit=round(Dezimal(credit_limit.get("quantity") or 0), 2),
                    used=round(Dezimal(drawn_amount.get("quantity") or 0), 2),
                    active=active,
                    related_account=related_account,
                )
            )

        return cards

    async def global_position(self) -> GlobalPosition:
        accounts, _, accounts_by_bban = await self._build_accounts()
        cards = await self._build_cards(accounts_by_bban)

        products = {}
        if accounts:
            products[ProductType.ACCOUNT] = Accounts(accounts)
        if cards:
            products[ProductType.CARD] = Cards(cards)

        return GlobalPosition(id=uuid4(), entity=B100, products=products)

    @staticmethod
    def _is_interest(movement: dict) -> bool:
        detail = movement.get("detail") or ""
        return movement.get("movementSubtype") == "BaseMovement" and detail.startswith(
            "INTERESES"
        )

    @staticmethod
    def _parse_date(value: Optional[str]) -> datetime:
        if value:
            try:
                normalized = value.replace("Z", "+00:00")
                match = re.match(r"^(.*\.\d{6})\d*([+-]\d{2}:\d{2})$", normalized)
                if match:
                    normalized = match.group(1) + match.group(2)
                return datetime.fromisoformat(normalized).astimezone(tzlocal())
            except Exception:
                pass
        return datetime.now(tzlocal())

    def _map_interest_tx(self, movement: dict) -> AccountTx:
        amount = movement.get("amount") or {}
        net = Dezimal(amount.get("quantity") or 0)
        gross = net / (1 - CAPITAL_GAINS_BASE_TAX)
        retentions = gross - net

        return AccountTx(
            id=uuid4(),
            ref=movement["id"],
            name=movement.get("detail") or "INTERESES",
            amount=round(gross, 2),
            currency=amount.get("currency"),
            type=TxType.INTEREST,
            date=self._parse_date(movement.get("transactionDate")),
            entity=B100,
            source=DataSource.REAL,
            product_type=ProductType.ACCOUNT,
            fees=Dezimal(0),
            retentions=round(retentions, 2),
            net_amount=round(net, 2),
        )

    async def transactions(
        self, registered_txs: set[str], options: FetchOptions
    ) -> Transactions:
        raw_accounts = await self._client.get_accounts() or []
        account_txs: list[AccountTx] = []

        for entry in raw_accounts:
            account_raw_id = entry.get("id")
            if not account_raw_id:
                continue

            cursor = None
            stop = False
            while not stop:
                page = await self._client.get_account_movements(
                    account_raw_id, page_size=MOVEMENTS_PAGE_SIZE, cursor=cursor
                )
                movements = page.get("data") or []

                for movement in movements:
                    if not self._is_interest(movement):
                        continue
                    if movement["id"] in registered_txs:
                        if not options.deep:
                            stop = True
                            break
                        continue
                    account_txs.append(self._map_interest_tx(movement))

                cursor = (page.get("pagination") or {}).get("next")
                if not cursor or not movements:
                    break

        return Transactions(account=account_txs)
