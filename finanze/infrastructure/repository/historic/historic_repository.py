from datetime import datetime
from typing import Dict, List
from uuid import UUID

from application.ports.historic_port import HistoricPort
from dateutil.tz import tzlocal
from domain.dezimal import Dezimal
from domain.entity import Entity
from domain.historic import (
    BaseHistoricEntry,
    FactoringEntry,
    Historic,
    RealStateCFEntry,
)
from domain.global_position import ProductType
from domain.transactions import BaseInvestmentTx
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.transaction.transaction_repository import (
    _map_investment_row,
)


def _map_historic_row(row) -> BaseHistoricEntry:
    entity = Entity(
        id=UUID(row["entity_id"]),
        name=row["entity_name"],
        type=row["entity_type"],
        is_real=row["entity_is_real"],
    )

    common = {
        "id": UUID(row["id"]),
        "name": row["name"],
        "invested": Dezimal(row["invested"]),
        "repaid": Dezimal(row["repaid"]) if row["repaid"] else None,
        "returned": Dezimal(row["returned"]) if row["returned"] else None,
        "currency": row["currency"],
        "last_invest_date": datetime.fromisoformat(row["last_invest_date"]),
        "last_tx_date": datetime.fromisoformat(row["last_tx_date"]),
        "effective_maturity": datetime.fromisoformat(row["effective_maturity"])
        if row["effective_maturity"]
        else None,
        "net_return": Dezimal(row["net_return"]) if row["net_return"] else None,
        "fees": Dezimal(row["fees"]) if row["fees"] else None,
        "retentions": Dezimal(row["retentions"]) if row["retentions"] else None,
        "interests": Dezimal(row["interests"]) if row["interests"] else None,
        "state": row["state"],
        "entity": entity,
        "product_type": ProductType(row["product_type"]),
        "related_txs": [],
    }

    if common["product_type"] == ProductType.FACTORING:
        return FactoringEntry(
            **common,
            interest_rate=Dezimal(row["interest_rate"]),
            gross_interest_rate=Dezimal(row["gross_interest_rate"]),
            maturity=datetime.fromisoformat(row["maturity"]).date(),
            type=row["type"],
        )
    elif common["product_type"] == ProductType.REAL_STATE_CF:
        return RealStateCFEntry(
            **common,
            interest_rate=Dezimal(row["interest_rate"]),
            maturity=datetime.fromisoformat(row["maturity"]).date(),
            extended_maturity=row["extended_maturity"]
            if "extended_maturity" in row
            else None,
            type=row["type"],
            business_type=row["business_type"],
        )


def _map_transaction_row(row) -> BaseInvestmentTx:
    return _map_investment_row(row)


class HistoricSQLRepository(HistoricPort):
    def __init__(self, client: DBClient):
        self._db_client = client

    def save(self, entries: list[BaseHistoricEntry]):
        with self._db_client.tx() as cursor:
            for entry in entries:
                base_data = {
                    "id": str(entry.id),
                    "name": entry.name,
                    "invested": str(entry.invested),
                    "repaid": str(entry.repaid) if entry.repaid else None,
                    "returned": str(entry.returned) if entry.returned else None,
                    "currency": entry.currency,
                    "last_invest_date": entry.last_invest_date.isoformat(),
                    "last_tx_date": entry.last_tx_date.isoformat(),
                    "effective_maturity": entry.effective_maturity.isoformat()
                    if entry.effective_maturity
                    else None,
                    "net_return": str(entry.net_return) if entry.net_return else None,
                    "fees": str(entry.fees) if entry.fees else None,
                    "retentions": str(entry.retentions) if entry.retentions else None,
                    "interests": str(entry.interests) if entry.interests else None,
                    "state": entry.state,
                    "entity_id": str(entry.entity.id),
                    "product_type": entry.product_type.value,
                    "created_at": datetime.now(tzlocal()).isoformat(),
                    "interest_rate": None,
                    "gross_interest_rate": None,
                    "maturity": None,
                    "extended_maturity": None,
                    "type": None,
                    "business_type": None,
                }

                if isinstance(entry, FactoringEntry):
                    base_data.update(
                        {
                            "interest_rate": str(entry.interest_rate),
                            "gross_interest_rate": str(entry.gross_interest_rate),
                            "maturity": entry.maturity.isoformat(),
                            "type": entry.type,
                        }
                    )
                elif isinstance(entry, RealStateCFEntry):
                    base_data.update(
                        {
                            "interest_rate": str(entry.interest_rate),
                            "maturity": entry.maturity.isoformat(),
                            "extended_maturity": entry.extended_maturity,
                            "type": entry.type,
                            "business_type": entry.business_type,
                        }
                    )

                cursor.execute(
                    """
                               INSERT INTO investment_historic (id, name, invested, repaid, returned, currency,
                                                                last_invest_date,
                                                                last_tx_date, effective_maturity, net_return, fees,
                                                                retentions, interests, state, entity_id, product_type,
                                                                interest_rate, gross_interest_rate, maturity,
                                                                extended_maturity, type, business_type, created_at)
                               VALUES (:id, :name, :invested, :repaid, :returned, :currency, :last_invest_date,
                                       :last_tx_date, :effective_maturity, :net_return, :fees,
                                       :retentions, :interests, :state, :entity_id, :product_type,
                                       :interest_rate, :gross_interest_rate, :maturity,
                                       :extended_maturity, :type, :business_type, :created_at)
                               """,
                    base_data,
                )

                for tx in entry.related_txs:
                    cursor.execute(
                        """
                                   INSERT INTO investment_historic_txs
                                       (tx_id, historic_entry_id)
                                   VALUES (?, ?)
                                   """,
                        (str(tx.id), str(entry.id)),
                    )

    def get_all(self, fetch_related_txs: bool = False) -> Historic:
        with self._db_client.read() as cursor:
            cursor.execute("""
                           SELECT h.*, e.name AS entity_name, e.id AS entity_id, e.type as entity_type, e.is_real AS entity_is_real
                           FROM investment_historic h
                                    JOIN entities e ON h.entity_id = e.id
                           """)
            entries = cursor.fetchall()

            if not entries:
                return Historic(entries=[])

            tx_mapping: Dict[str, List[BaseInvestmentTx]] = {}

            if fetch_related_txs:
                entry_ids = [str(entry["id"]) for entry in entries]
                cursor.execute(
                    f"""
                    SELECT t.*, h_txs.historic_entry_id
                    FROM investment_historic_txs h_txs
                    JOIN investment_transactions t ON h_txs.tx_id = t.id
                    WHERE h_txs.historic_entry_id IN ({",".join(["?"] * len(entry_ids))})
                """,
                    entry_ids,
                )

                for row in cursor.fetchall():
                    entry_id = row["historic_entry_id"]
                    tx = _map_transaction_row(row)
                    if entry_id not in tx_mapping:
                        tx_mapping[entry_id] = []
                    tx_mapping[entry_id].append(tx)

            historic_entries = []
            for entry_row in entries:
                entry_id = str(entry_row["id"])
                historic_entry = _map_historic_row(entry_row)
                historic_entry.related_txs = (
                    tx_mapping.get(entry_id, []) if fetch_related_txs else []
                )
                historic_entries.append(historic_entry)

            return Historic(entries=historic_entries)

    def delete_by_entity(self, entity_id: UUID):
        with self._db_client.tx() as cursor:
            cursor.execute(
                "DELETE FROM investment_historic WHERE entity_id = ?", (str(entity_id),)
            )
