from uuid import UUID, uuid4

from application.ports.crypto_initial_investment_port import CryptoInitialInvestmentPort
from domain.global_position import CryptoInitialInvestment
from infrastructure.repository.db.client import DBClient


class CryptoInitialInvestmentRepository(CryptoInitialInvestmentPort):
    def __init__(self, client: DBClient):
        self._db_client = client

    def save(self, entries: list[CryptoInitialInvestment]):
        with self._db_client.tx() as cursor:
            for entry in entries:
                cursor.execute(
                    """
                    INSERT INTO crypto_initial_investments (id, wallet_connection_id, symbol, type, currency, initial_investment, average_buy_price)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid4()),
                        str(entry.wallet_connection_id),
                        entry.symbol,
                        entry.type,
                        entry.currency,
                        str(entry.initial_investment),
                        str(entry.average_buy_price),
                    ),
                )

    def delete_for_wallet_connection(self, wallet_connection_id: UUID):
        with self._db_client.tx() as cursor:
            cursor.execute(
                "DELETE FROM crypto_initial_investments WHERE wallet_connection_id = ?",
                (str(wallet_connection_id),),
            )
