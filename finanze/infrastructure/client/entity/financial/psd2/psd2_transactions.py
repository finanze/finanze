import hashlib
from datetime import date, datetime
from typing import Optional
from uuid import uuid4

from dateutil.tz import tzlocal
from domain.dezimal import Dezimal
from domain.entity import Entity
from domain.fetch_record import DataSource
from domain.global_position import ProductType
from domain.transactions import AccountTx, TxType, normalize_iban

MAX_NAME_LENGTH = 250
DEFAULT_MOVEMENT_NAME = "Movement"


def _clean(value) -> Optional[str]:
    if not value:
        return None
    if isinstance(value, list):
        value = " ".join(str(v) for v in value if v)
    text = " ".join(str(value).split())
    return text[:MAX_NAME_LENGTH] or None


def _parse_date(*values) -> Optional[date]:
    for value in values:
        if value:
            try:
                return date.fromisoformat(str(value)[:10])
            except ValueError:
                continue
    return None


def _fallback_ref(account_key: str, *parts) -> str:
    raw = "|".join([account_key, *[str(p or "") for p in parts]])
    return f"{account_key}:h{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:24]}"


def _build_tx(
    ref: str,
    name: Optional[str],
    counterparty: Optional[str],
    amount: Dezimal,
    currency: str,
    tx_type: TxType,
    tx_date: date,
    entity: Entity,
    iban: Optional[str] = None,
) -> AccountTx:
    return AccountTx(
        id=uuid4(),
        ref=ref,
        name=name or counterparty or DEFAULT_MOVEMENT_NAME,
        amount=amount,
        currency=currency,
        type=tx_type,
        date=datetime.combine(tx_date, datetime.min.time(), tzinfo=tzlocal()),
        entity=entity,
        source=DataSource.REAL,
        product_type=ProductType.ACCOUNT,
        fees=Dezimal(0),
        retentions=Dezimal(0),
        net_amount=amount,
        counterparty=counterparty,
        iban=normalize_iban(iban),
    )


def map_enablebanking_transaction(
    raw: dict, account_key: str, entity: Entity, iban: Optional[str] = None
) -> Optional[AccountTx]:
    if (raw.get("status") or "BOOK") != "BOOK":
        return None

    amount_data = raw.get("transaction_amount") or {}
    currency = amount_data.get("currency")
    raw_amount = amount_data.get("amount")
    tx_date = _parse_date(
        raw.get("booking_date"), raw.get("value_date"), raw.get("transaction_date")
    )
    if raw_amount is None or not currency or tx_date is None:
        return None

    amount = Dezimal(str(raw_amount))
    indicator = raw.get("credit_debit_indicator")
    if indicator == "DBIT":
        tx_type = TxType.OUTFLOW
    elif indicator == "CRDT":
        tx_type = TxType.INFLOW
    else:
        tx_type = TxType.OUTFLOW if amount < 0 else TxType.INFLOW
    amount = abs(amount)
    if amount == 0:
        return None

    party = raw.get("creditor") if tx_type == TxType.OUTFLOW else raw.get("debtor")
    counterparty = _clean((party or {}).get("name"))
    name = _clean(raw.get("remittance_information")) or _clean(
        (raw.get("bank_transaction_code") or {}).get("description")
    )

    entry_reference = raw.get("entry_reference")
    ref = (
        f"{account_key}:{entry_reference}"
        if entry_reference
        else _fallback_ref(
            account_key,
            tx_date.isoformat(),
            amount,
            currency,
            indicator,
            name,
            counterparty,
            (raw.get("balance_after_transaction") or {}).get("amount"),
        )
    )
    return _build_tx(
        ref, name, counterparty, amount, currency, tx_type, tx_date, entity, iban
    )


def map_gocardless_transaction(
    raw: dict, account_key: str, entity: Entity, iban: Optional[str] = None
) -> Optional[AccountTx]:
    amount_data = raw.get("transactionAmount") or {}
    currency = amount_data.get("currency")
    raw_amount = amount_data.get("amount")
    tx_date = _parse_date(
        raw.get("bookingDate"), raw.get("valueDate"), raw.get("bookingDateTime")
    )
    if raw_amount is None or not currency or tx_date is None:
        return None

    signed_amount = Dezimal(str(raw_amount))
    if signed_amount == 0:
        return None
    tx_type = TxType.OUTFLOW if signed_amount < 0 else TxType.INFLOW
    amount = abs(signed_amount)

    counterparty = _clean(
        raw.get("creditorName") if tx_type == TxType.OUTFLOW else raw.get("debtorName")
    )
    name = (
        _clean(raw.get("remittanceInformationUnstructured"))
        or _clean(raw.get("remittanceInformationUnstructuredArray"))
        or _clean(raw.get("remittanceInformationStructured"))
        or _clean(raw.get("additionalInformation"))
    )

    tx_id = raw.get("transactionId") or raw.get("internalTransactionId")
    ref = (
        f"{account_key}:{tx_id}"
        if tx_id
        else _fallback_ref(
            account_key,
            tx_date.isoformat(),
            signed_amount,
            currency,
            name,
            counterparty,
            raw.get("entryReference"),
        )
    )
    return _build_tx(
        ref, name, counterparty, amount, currency, tx_type, tx_date, entity, iban
    )
