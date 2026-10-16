import random
from datetime import datetime
from typing import Optional
from uuid import UUID

from application.ports.transaction_label_port import TransactionLabelPort
from dateutil.tz import tzlocal
from domain.fetch_record import DataSource
from domain.transactions import AccountTx, LabelOrigin, TxClassification, TxLabel
from infrastructure.repository.db.client import DBClient, DBCursor
from infrastructure.repository.labeling.common import (
    chunked,
    load_transfer_pairs,
    load_tx_labels,
    placeholders,
)
from infrastructure.repository.labeling.queries import TransactionLabelQueries
from infrastructure.repository.transaction.queries import TransactionQueries
from infrastructure.repository.transaction.transaction_repository import (
    map_account_row,
)


class TransactionLabelRepository(TransactionLabelPort):
    def __init__(self, client: DBClient):
        self._db_client = client

    async def get_by_tx_ids(self, tx_ids: list[UUID]) -> dict[UUID, list[TxLabel]]:
        if not tx_ids:
            return {}
        async with self._db_client.read() as cursor:
            return await load_tx_labels(cursor, tx_ids)

    async def add(self, tx_id: UUID, labels: list[TxLabel]):
        if not labels:
            return
        now = datetime.now(tzlocal()).isoformat()
        async with self._db_client.tx() as cursor:
            for label in labels:
                await cursor.execute(
                    TransactionLabelQueries.INSERT,
                    (
                        str(tx_id),
                        str(label.label_id),
                        label.origin.value,
                        str(label.rule_id) if label.rule_id else None,
                        label.provider,
                        str(label.confidence) if label.confidence is not None else None,
                        now,
                    ),
                )

    async def delete(
        self, tx_ids: list[UUID], origins: Optional[list[LabelOrigin]] = None
    ):
        if not tx_ids:
            return
        async with self._db_client.tx() as cursor:
            for chunk in chunked([str(tx_id) for tx_id in tx_ids]):
                query = f"DELETE FROM account_transaction_labels WHERE tx_id IN ({placeholders(chunk)})"
                params: list = list(chunk)
                if origins:
                    query += f" AND origin IN ({placeholders(origins)})"
                    params.extend([o.value for o in origins])
                await cursor.execute(query, tuple(params))

    async def delete_by_rule(self, rule_id: UUID):
        async with self._db_client.tx() as cursor:
            await cursor.execute(
                TransactionLabelQueries.DELETE_BY_RULE, (str(rule_id),)
            )

    async def set_locked(self, tx_ids: list[UUID], locked: bool):
        if not tx_ids:
            return
        async with self._db_client.tx() as cursor:
            for chunk in chunked([str(tx_id) for tx_id in tx_ids]):
                await cursor.execute(
                    f"UPDATE account_transactions SET labels_locked = ? WHERE id IN ({placeholders(chunk)})",
                    (locked, *chunk),
                )

    async def set_linked_tx(self, tx_id: UUID, linked_tx: Optional[str]):
        async with self._db_client.tx() as cursor:
            await cursor.execute(
                TransactionLabelQueries.SET_LINKED_TX, (linked_tx, str(tx_id))
            )

    async def set_external_unmatched(
        self, tx_ids: list[UUID], unmatched_at: Optional[datetime]
    ):
        if not tx_ids:
            return
        value = unmatched_at.isoformat() if unmatched_at else None
        async with self._db_client.tx() as cursor:
            for chunk in chunked([str(tx_id) for tx_id in tx_ids]):
                await cursor.execute(
                    f"UPDATE account_transactions SET external_unmatched_at = ? WHERE id IN ({placeholders(chunk)})",
                    (value, *chunk),
                )

    async def get_linked_refs(self, entity_ids: list[UUID]) -> set[tuple[UUID, str]]:
        if not entity_ids:
            return set()
        async with self._db_client.read() as cursor:
            await cursor.execute(
                f"""
                SELECT entity_id, linked_tx
                FROM account_transactions
                WHERE linked_tx IS NOT NULL AND entity_id IN ({placeholders(entity_ids)})
                """,
                tuple(str(e) for e in entity_ids),
            )
            return {
                (UUID(row["entity_id"]), row["linked_tx"])
                for row in await cursor.fetchall()
            }

    async def add_transfer_pair(
        self, tx_id: UUID, paired_tx_id: UUID, rule_id: Optional[UUID]
    ):
        now = datetime.now(tzlocal()).isoformat()
        rule = str(rule_id) if rule_id else None
        async with self._db_client.tx() as cursor:
            await cursor.execute(
                TransactionLabelQueries.INSERT_TRANSFER_PAIR,
                (str(tx_id), str(paired_tx_id), rule, now),
            )
            await cursor.execute(
                TransactionLabelQueries.INSERT_TRANSFER_PAIR,
                (str(paired_tx_id), str(tx_id), rule, now),
            )

    async def delete_transfer_pair(self, tx_id: UUID):
        async with self._db_client.tx() as cursor:
            await cursor.execute(
                TransactionLabelQueries.DELETE_TRANSFER_PAIR, (str(tx_id), str(tx_id))
            )

    async def delete_transfer_pairs_by_rule(self, rule_id: UUID):
        async with self._db_client.tx() as cursor:
            await cursor.execute(
                TransactionLabelQueries.DELETE_TRANSFER_PAIRS_BY_RULE, (str(rule_id),)
            )

    async def delete_unpaired_rule_labels(self, rule_ids: list[UUID]):
        if not rule_ids:
            return
        async with self._db_client.tx() as cursor:
            await cursor.execute(
                f"""
                DELETE FROM account_transaction_labels
                WHERE origin = 'RULE'
                  AND rule_id IN ({placeholders(rule_ids)})
                  AND tx_id IN (SELECT id FROM account_transactions WHERE labels_locked = FALSE)
                  AND tx_id NOT IN (SELECT tx_id FROM account_transfer_pairs)
                """,
                tuple(str(rule_id) for rule_id in rule_ids),
            )

    async def _restore_transfer_pair(self, cursor: DBCursor, tx_id: UUID, pair):
        for candidate in (tx_id, pair.tx_id):
            await cursor.execute(
                TransactionLabelQueries.GET_TRANSFER_PAIR, (str(candidate),)
            )
            if await cursor.fetchone():
                return
        await cursor.execute(TransactionLabelQueries.TX_EXISTS, (str(pair.tx_id),))
        if not await cursor.fetchone():
            return
        await self.add_transfer_pair(tx_id, pair.tx_id, pair.rule_id)

    async def _load_classifications(
        self, cursor: DBCursor, where: str, params: tuple
    ) -> list[tuple[UUID, UUID, str, TxClassification]]:
        await cursor.execute(
            f"{TransactionLabelQueries.CLASSIFICATION_BASE.value} WHERE {where} AND {TransactionLabelQueries.CLASSIFICATION_FILTER.value}",
            params,
        )
        rows = await cursor.fetchall()
        ids = [UUID(row["id"]) for row in rows]
        labels = await load_tx_labels(cursor, ids)
        pairs = await load_transfer_pairs(cursor, ids)
        return [
            (
                UUID(row["id"]),
                UUID(row["entity_id"]),
                row["ref"],
                TxClassification(
                    labels=labels.get(UUID(row["id"]), []),
                    locked=bool(row["labels_locked"]),
                    linked_tx=row["linked_tx"],
                    transfer_pair=pairs.get(UUID(row["id"])),
                    external_unmatched_at=datetime.fromisoformat(
                        row["external_unmatched_at"]
                    )
                    if row["external_unmatched_at"]
                    else None,
                ),
            )
            for row in rows
        ]

    async def get_classifications_by_entity_account(
        self, entity_account_id: UUID
    ) -> dict[tuple[UUID, str], TxClassification]:
        async with self._db_client.read() as cursor:
            entries = await self._load_classifications(
                cursor, "at.entity_account_id = ?", (str(entity_account_id),)
            )
        return {(entity_id, ref): c for _, entity_id, ref, c in entries}

    async def get_classifications_by_source(
        self, source: DataSource
    ) -> dict[tuple[UUID, str], TxClassification]:
        async with self._db_client.read() as cursor:
            entries = await self._load_classifications(
                cursor, "at.source = ?", (source.value,)
            )
        return {(entity_id, ref): c for _, entity_id, ref, c in entries}

    async def get_classifications_by_ids(
        self, tx_ids: list[UUID]
    ) -> dict[UUID, TxClassification]:
        if not tx_ids:
            return {}
        result = {}
        async with self._db_client.read() as cursor:
            for chunk in chunked([str(tx_id) for tx_id in tx_ids]):
                entries = await self._load_classifications(
                    cursor, f"at.id IN ({placeholders(chunk)})", tuple(chunk)
                )
                result.update({tx_id: c for tx_id, _, _, c in entries})
        return result

    async def restore(self, classifications: dict[UUID, TxClassification]):
        if not classifications:
            return
        async with self._db_client.tx() as cursor:
            for tx_id, classification in classifications.items():
                if classification.locked:
                    await self.set_locked([tx_id], True)
                if classification.linked_tx:
                    await self.set_linked_tx(tx_id, classification.linked_tx)
                if classification.external_unmatched_at:
                    await self.set_external_unmatched(
                        [tx_id], classification.external_unmatched_at
                    )
                if classification.transfer_pair:
                    await self._restore_transfer_pair(
                        cursor, tx_id, classification.transfer_pair
                    )
                await self.add(tx_id, classification.labels)

    async def get_examples(
        self, origins: list[LabelOrigin], per_label: int, limit: int
    ) -> list[AccountTx]:
        if not origins or per_label <= 0 or limit <= 0:
            return []
        async with self._db_client.read() as cursor:
            await cursor.execute(
                f"""
                SELECT label_id, tx_id
                FROM account_transaction_labels
                WHERE origin IN ({placeholders(origins)})
                """,
                tuple(o.value for o in origins),
            )
            by_label: dict[str, list[str]] = {}
            for row in await cursor.fetchall():
                by_label.setdefault(row["label_id"], []).append(row["tx_id"])

            selected: list[str] = []
            label_ids = list(by_label.keys())
            random.shuffle(label_ids)
            for label_id in label_ids:
                tx_ids = by_label[label_id]
                random.shuffle(tx_ids)
                for tx_id in tx_ids[:per_label]:
                    if tx_id not in selected:
                        selected.append(tx_id)
                if len(selected) >= limit:
                    break
            selected = selected[:limit]
            if not selected:
                return []

            await cursor.execute(
                f"{TransactionQueries.ACCOUNT_SELECT_BASE.value} AND at.id IN ({placeholders(selected)})",
                tuple(selected),
            )
            txs = [map_account_row(row) for row in await cursor.fetchall()]
            labels = await load_tx_labels(cursor, [tx.id for tx in txs])
            for tx in txs:
                tx.labels = labels.get(tx.id, [])
            return txs
