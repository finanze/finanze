import logging
from contextlib import asynccontextmanager
from datetime import datetime
from threading import RLock
from types import TracebackType
from typing import Any, AsyncGenerator, Literal, Optional, Self
from uuid import uuid4

from domain.data_init import DataEncryptedError

UnderlyingCursor = Any
UnderlyingConnection = Any


class DBCursor:
    def __init__(self, cursor: UnderlyingCursor) -> None:
        self._cursor = cursor

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exctype: Optional[BaseException],
        value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> Literal[False]:
        await self.close()
        return False

    def __iter__(self) -> Self:
        return self

    def __next__(self) -> Any:
        result = next(self._cursor, None)
        if result is None:
            raise StopIteration

        return result

    async def execute(self, statement: str, *args) -> Self:
        self._cursor.execute(statement, *args)
        return self

    async def execute_script(self, script: str) -> Self:
        self._cursor.executescript(script)
        return self

    async def fetchone(self) -> Any:
        return self._cursor.fetchone()

    async def fetchmany(self, size: Optional[int] = None) -> list[Any]:
        return self._cursor.fetchmany(size)

    async def fetchall(self) -> list[Any]:
        return self._cursor.fetchall()

    async def close(self) -> None:
        self._cursor.close()


class DBClient:
    def __init__(self, connection: UnderlyingConnection | None = None):
        self._conn = connection
        self.savepoint_stack: list[Optional[str]] = []
        self._lock = RLock()
        self._log = logging.getLogger(__name__)

    def _get_connection(self) -> UnderlyingConnection:
        if self._conn is None:
            raise DataEncryptedError()
        return self._conn

    @asynccontextmanager
    async def tx(self, skip_last_update=False) -> AsyncGenerator[DBCursor, None]:
        with self._lock:
            cursor = self._cursor()
            try:
                if not self.savepoint_stack:
                    # Outer transaction
                    await cursor.execute("BEGIN")
                    self.savepoint_stack.append(None)
                else:
                    # Generate unique savepoint name for nested transaction
                    savepoint_name = f"savepoint_{uuid4().hex}"
                    await cursor.execute(f"SAVEPOINT {savepoint_name}")
                    self.savepoint_stack.append(savepoint_name)
                yield cursor

            except Exception:
                if self.savepoint_stack:
                    current_sp = self.savepoint_stack[-1]
                    if current_sp is not None:
                        # Rollback to savepoint and release it
                        await cursor.execute(f"ROLLBACK TO SAVEPOINT {current_sp}")
                        await cursor.execute(f"RELEASE SAVEPOINT {current_sp}")
                    else:
                        # Rollback outermost transaction
                        self._rollback()
                raise  # Re-raise exception
            else:
                if self.savepoint_stack:
                    current_sp = self.savepoint_stack[-1]
                    if current_sp is not None:
                        # Release savepoint (commit nested changes)
                        await cursor.execute(f"RELEASE SAVEPOINT {current_sp}")
                    else:
                        # Save last update date and commit outermost transaction
                        if not skip_last_update:
                            await self._update_last_update_date()
                        self._commit()
            finally:
                # Cleanup stack and cursor
                if self.savepoint_stack:
                    self.savepoint_stack.pop()
                await cursor.close()

    @asynccontextmanager
    async def read(self) -> AsyncGenerator[DBCursor, None]:
        with self._lock:
            cursor = self._cursor()
            try:
                yield cursor
            finally:
                await cursor.close()

    async def _update_last_update_date(self):
        timestamp = datetime.now().astimezone().isoformat()
        cursor = self._cursor()
        try:
            await cursor.execute(
                "INSERT OR REPLACE INTO sys_config (key, value) VALUES (?, ?)",
                ("last_update", timestamp),
            )
        finally:
            await cursor.close()

    def _commit(self):
        self._get_connection().commit()

    def _rollback(self):
        self._get_connection().rollback()

    async def close(self):
        with self._lock:
            self._get_connection().close()
            self._conn = None

    async def silent_close(self) -> bool:
        try:
            await self.close()
            return True
        except Exception:
            return False

    async def wal_checkpoint(self, mode: str = "PASSIVE") -> None:
        with self._lock:
            # We can't use async context manager with synchronous 'with' safely without care,
            # but here we are inside an async method.
            async with self.read() as cursor:
                await cursor.execute(f"PRAGMA wal_checkpoint({mode})")

    def _cursor(self) -> DBCursor:
        return DBCursor(self._get_connection().cursor())

    def set_connection(self, connection: UnderlyingConnection) -> None:
        self._conn = connection
        self.savepoint_stack = []
