from contextlib import contextmanager
from types import TracebackType
from typing import Optional, Literal, Any, Generator
from uuid import uuid4

from pysqlcipher3 import dbapi2 as sqlcipher
from typing_extensions import TypeAlias, Self

UnderlyingCursor: TypeAlias = sqlcipher.Cursor
UnderlyingConnection: TypeAlias = sqlcipher.Connection


class DBCursor:

    def __init__(self, cursor: UnderlyingCursor) -> None:
        self._cursor = cursor

    def __enter__(self) -> Self:
        return self

    def __exit__(
            self,
            exctype: Optional[BaseException],
            value: Optional[BaseException],
            traceback: Optional[TracebackType],
    ) -> Literal[False]:
        self.close()
        return False

    def __iter__(self) -> Self:
        return self

    def __next__(self) -> Any:
        result = next(self._cursor, None)
        if result is None:
            raise StopIteration

        return result

    def execute(self, statement: str, *args) -> Self:
        return self._cursor.execute(statement, *args)

    def fetchone(self) -> Any:
        return self._cursor.fetchone()

    def fetchmany(self, size: Optional[int] = None) -> list[Any]:
        return self._cursor.fetchmany(size)

    def fetchall(self) -> list[Any]:
        return self._cursor.fetchall()

    def close(self) -> None:
        self._cursor.close()


class DBClient:

    def __init__(self, connection: UnderlyingConnection | None = None):
        self._conn = connection
        self.savepoint_stack: list[Optional[str]] = []

    def _get_connection(self) -> UnderlyingConnection:
        if self._conn is None:
            raise RuntimeError("There's no active connection.")
        return self._conn

    @contextmanager
    def tx(self) -> Generator[DBCursor, None, None]:
        cursor = self.cursor()
        try:
            if not self.savepoint_stack:
                # Outer transaction
                cursor.execute("BEGIN")
                self.savepoint_stack.append(None)
            else:
                # Generate unique savepoint name for nested transaction
                savepoint_name = f"savepoint_{uuid4().hex}"
                cursor.execute(f"SAVEPOINT {savepoint_name}")
                self.savepoint_stack.append(savepoint_name)
            yield cursor

        except Exception as e:
            if self.savepoint_stack:
                current_sp = self.savepoint_stack[-1]
                if current_sp is not None:
                    # Rollback to savepoint and release it
                    cursor.execute(f"ROLLBACK TO SAVEPOINT {current_sp}")
                    cursor.execute(f"RELEASE SAVEPOINT {current_sp}")
                else:
                    # Rollback outermost transaction
                    self.rollback()
            raise  # Re-raise exception
        else:
            if self.savepoint_stack:
                current_sp = self.savepoint_stack[-1]
                if current_sp is not None:
                    # Release savepoint (commit nested changes)
                    cursor.execute(f"RELEASE SAVEPOINT {current_sp}")
                else:
                    # Commit outermost transaction
                    self.commit()
        finally:
            # Cleanup stack and cursor
            if self.savepoint_stack:
                self.savepoint_stack.pop()
            cursor.close()

    @contextmanager
    def read(self) -> Generator[DBCursor, None, None]:
        cursor = self.cursor()
        try:
            yield cursor
        finally:
            cursor.close()

    def commit(self):
        self._get_connection().commit()

    def rollback(self):
        self._get_connection().rollback()

    def close(self):
        self._get_connection().close()

    def cursor(self) -> DBCursor:
        return DBCursor(self._get_connection().cursor())

    def set_connection(self, connection: UnderlyingConnection) -> None:
        self._conn = connection
        self.savepoint_stack = []
