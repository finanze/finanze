from contextlib import asynccontextmanager

from application.ports.transaction_handler_port import TransactionHandlerPort
from infrastructure.repository.db.client import DBClient


class TransactionHandler(TransactionHandlerPort):
    def __init__(self, client: DBClient):
        self._db_client = client

    @asynccontextmanager
    async def start(self):
        async with self._db_client.tx() as _:
            yield
