from typing import Iterable, TypeVar
from uuid import UUID

from domain.dezimal import Dezimal
from domain.transactions import LabelOrigin, TransferPair, TxLabel
from infrastructure.repository.db.client import DBCursor

T = TypeVar("T")

SQL_CHUNK_SIZE = 500


def chunked(items: list[T], size: int = SQL_CHUNK_SIZE) -> Iterable[list[T]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]


def placeholders(items: list) -> str:
    return ", ".join("?" for _ in items)


def map_tx_label_row(row) -> TxLabel:
    return TxLabel(
        label_id=UUID(row["label_id"]),
        origin=LabelOrigin(row["origin"]),
        rule_id=UUID(row["rule_id"]) if row["rule_id"] else None,
        provider=row["provider"],
        confidence=Dezimal(row["confidence"]) if row["confidence"] else None,
    )


async def load_tx_labels(
    cursor: DBCursor, tx_ids: list[UUID]
) -> dict[UUID, list[TxLabel]]:
    result: dict[UUID, list[TxLabel]] = {}
    str_ids = [str(tx_id) for tx_id in tx_ids]
    for chunk in chunked(str_ids):
        await cursor.execute(
            f"""
            SELECT tx_id, label_id, origin, rule_id, provider, confidence
            FROM account_transaction_labels
            WHERE tx_id IN ({placeholders(chunk)})
            ORDER BY created_at, label_id
            """,
            tuple(chunk),
        )
        for row in await cursor.fetchall():
            result.setdefault(UUID(row["tx_id"]), []).append(map_tx_label_row(row))
    return result


async def load_transfer_pairs(
    cursor: DBCursor, tx_ids: list[UUID]
) -> dict[UUID, TransferPair]:
    result: dict[UUID, TransferPair] = {}
    str_ids = [str(tx_id) for tx_id in tx_ids]
    for chunk in chunked(str_ids):
        await cursor.execute(
            f"""
            SELECT p.tx_id, p.paired_tx_id, p.rule_id, at.entity_id
            FROM account_transfer_pairs p
                JOIN account_transactions at ON at.id = p.paired_tx_id
            WHERE p.tx_id IN ({placeholders(chunk)})
            """,
            tuple(chunk),
        )
        for row in await cursor.fetchall():
            result[UUID(row["tx_id"])] = TransferPair(
                tx_id=UUID(row["paired_tx_id"]),
                entity_id=UUID(row["entity_id"]),
                rule_id=UUID(row["rule_id"]) if row["rule_id"] else None,
            )
    return result
