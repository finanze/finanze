import logging
import re
from contextlib import asynccontextmanager
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, AsyncGenerator, Literal, Optional
from uuid import UUID
from uuid import uuid4

from domain.data_init import DataEncryptedError
from domain.dezimal import Dezimal

try:
    import js  # type: ignore
except Exception:  # pragma: no cover
    js = None

try:
    from pyodide.ffi import to_js  # type: ignore
except Exception:  # pragma: no cover
    to_js = None

UnderlyingCursor = Any
UnderlyingConnection = Any


def _is_js_nullish(value: Any) -> bool:
    try:
        return type(value).__name__ in ("JsNull", "JsUndefined")
    except Exception:
        return False


def _normalize_js_nullish(value: Any) -> Any:
    return None if _is_js_nullish(value) else value


class _ReentrantAsyncLock:
    def __init__(self):
        self._lock = __import__("asyncio").Lock()
        self._owner: Any | None = None
        self._depth = 0

    async def acquire(self) -> bool:
        asyncio = __import__("asyncio")
        task = asyncio.current_task()
        if self._owner is task:
            self._depth += 1
            return True

        await self._lock.acquire()
        self._owner = task
        self._depth = 1
        return True

    def release(self) -> None:
        asyncio = __import__("asyncio")
        task = asyncio.current_task()
        if self._owner is not task:
            raise RuntimeError("Lock can only be released by the owner task")

        self._depth -= 1
        if self._depth == 0:
            self._owner = None
            self._lock.release()

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.release()
        return False


class RowProxy:
    def __init__(self, row: Any):
        if isinstance(row, RowProxy):
            self._mapping = row._mapping
            self._keys = row._keys
            self._values = row._values
            return

        if isinstance(row, dict):
            self._mapping = row
            self._keys = list(row.keys())
            self._values = [_normalize_js_nullish(row[k]) for k in self._keys]
            return

        if isinstance(row, (list, tuple)):
            self._mapping = None
            self._keys = []
            self._values = [_normalize_js_nullish(v) for v in row]
            return

        self._mapping = None
        self._keys = []
        self._values = [_normalize_js_nullish(row)]

    def __getitem__(self, key: int | str):
        if isinstance(key, int):
            return self._values[key]
        if self._mapping is None:
            raise KeyError(key)
        return self._mapping[key]

    def __iter__(self):
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def keys(self) -> list[str]:
        return list(self._keys)


def _to_py(value: Any) -> Any:
    if _is_js_nullish(value):
        return None

    try:
        to_py = getattr(value, "to_py", None)
        if callable(to_py):
            converted = to_py()
            return _to_py(converted)
    except Exception:
        pass

    if isinstance(value, dict):
        return {k: _to_py(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_py(v) for v in value]

    return value


def _coerce_params(args: tuple[Any, ...]) -> Any:
    if not args:
        return []
    if len(args) == 1:
        single = args[0]
        if isinstance(single, dict):
            return {k: _normalize_param_for_js(v) for k, v in single.items()}
        if isinstance(single, (tuple, list)):
            return [_normalize_param_for_js(v) for v in single]

    return [_normalize_param_for_js(v) for v in args]


def _to_js_params(params: Any) -> Any:
    if to_js is None:
        return params
    try:
        return to_js(params, create_pyproxies=False)
    except Exception:
        return params


_NAMED_PARAM_RE = re.compile(r":([A-Za-z_][A-Za-z0-9_]*)")


def _rewrite_named_params(
    statement: str, params: dict[str, Any]
) -> tuple[str, list[Any]]:
    names = _NAMED_PARAM_RE.findall(statement)
    if not names:
        return statement, []
    rewritten = _NAMED_PARAM_RE.sub("?", statement)
    values = [params[name] for name in names]
    return rewritten, values


def _normalize_param_for_js(value: Any) -> Any:
    if value is None or _is_js_nullish(value):
        return None

    if isinstance(value, bool):
        return 1 if value else 0

    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            dt = dt.astimezone()
        return dt.isoformat()

    if isinstance(value, date):
        return value.isoformat()

    if isinstance(value, Dezimal):
        return str(value)

    if isinstance(value, Decimal):
        return format(value, "f")

    if isinstance(value, UUID):
        return str(value)

    if isinstance(value, Enum):
        inner = value.value
        if isinstance(inner, bool):
            return 1 if inner else 0
        if isinstance(inner, (str, int)):
            return inner
        return str(inner)

    return value


def _is_query_statement(statement: str) -> bool:
    stmt = " ".join(statement.strip().split()).upper()
    if not stmt:
        return False

    if stmt.startswith(("SELECT", "WITH", "EXPLAIN")):
        return True

    if stmt.startswith("PRAGMA"):
        if "=" in stmt:
            return False
        if stmt.startswith("PRAGMA KEY"):
            return False
        if "REKEY" in stmt:
            return False
        return True

    return False


class CapacitorDBCursor:
    def __init__(self) -> None:
        self._log = logging.getLogger(__name__)
        self._rows: list[RowProxy] = []
        self._fetch_index = 0

    def __iter__(self):
        return self

    def __next__(self) -> RowProxy:
        if self._fetch_index >= len(self._rows):
            raise StopIteration
        row = self._rows[self._fetch_index]
        self._fetch_index += 1
        return row

    async def __aenter__(self) -> "CapacitorDBCursor":
        return self

    async def __aexit__(
        self,
        exctype: Optional[BaseException],
        value: Optional[BaseException],
        traceback: Optional[Any],
    ) -> Literal[False]:
        await self.close()
        return False

    async def execute(self, statement: str, *args) -> "CapacitorDBCursor":
        if js is None:
            raise RuntimeError("Pyodide JS bridge is not available")

        params = _coerce_params(args)
        sql = statement
        values: list[Any]

        if isinstance(params, dict):
            sql, values = _rewrite_named_params(statement, params)
        else:
            values = params

        js_params = _to_js_params(values)
        self._rows = []
        self._fetch_index = 0

        try:
            if _is_query_statement(statement):
                res = await js.jsBridge.sqlite.querySql(sql, js_params)
                py = _to_py(res)
                self._rows = [RowProxy(r) for r in (list(py) if py else [])]
            else:
                await js.jsBridge.sqlite.executeSql(sql, js_params)
        except Exception as e:
            self._log.error(
                "Capacitor DB error: %s | SQL: %s | Args: %s",
                e,
                sql,
                values,
            )
            raise

        return self

    async def execute_script(self, script: str) -> "CapacitorDBCursor":
        if js is None:
            raise RuntimeError("Pyodide JS bridge is not available")

        self._rows = []
        self._fetch_index = 0

        await js.jsBridge.sqlite.executeBatch(script, True)
        return self

    async def fetchone(self) -> Any:
        if self._fetch_index >= len(self._rows):
            return None
        row = self._rows[self._fetch_index]
        self._fetch_index += 1
        return row

    async def fetchmany(self, size: Optional[int] = None) -> list[Any]:
        if size is None or size < 0:
            size = len(self._rows)

        start = self._fetch_index
        end = min(len(self._rows), start + size)
        self._fetch_index = end
        return self._rows[start:end]

    async def fetchall(self) -> list[Any]:
        start = self._fetch_index
        self._fetch_index = len(self._rows)
        return self._rows[start:]

    async def close(self) -> None:
        return


class CapacitorDBClient:
    def __init__(self, connection: UnderlyingConnection | None = None):
        self._conn = connection
        self.savepoint_stack: list[Optional[str]] = []
        self._lock = _ReentrantAsyncLock()
        self._log = logging.getLogger(__name__)

    def _get_connection(self) -> UnderlyingConnection:
        if self._conn is None:
            raise DataEncryptedError()
        return self._conn

    def _cursor(self) -> CapacitorDBCursor:
        self._get_connection()
        return CapacitorDBCursor()

    @asynccontextmanager
    async def tx(
        self, skip_last_update: bool = False
    ) -> AsyncGenerator[CapacitorDBCursor, None]:
        async with self._lock:
            cursor = self._cursor()
            try:
                if not self.savepoint_stack:
                    await cursor.execute("BEGIN")
                    self.savepoint_stack.append(None)
                else:
                    savepoint_name = f"savepoint_{uuid4().hex}"
                    await cursor.execute(f"SAVEPOINT {savepoint_name}")
                    self.savepoint_stack.append(savepoint_name)

                yield cursor

            except Exception:
                if self.savepoint_stack:
                    current_sp = self.savepoint_stack[-1]
                    if current_sp is not None:
                        await cursor.execute(f"ROLLBACK TO SAVEPOINT {current_sp}")
                        await cursor.execute(f"RELEASE SAVEPOINT {current_sp}")
                    else:
                        await cursor.execute("ROLLBACK")
                raise

            else:
                if self.savepoint_stack:
                    current_sp = self.savepoint_stack[-1]
                    if current_sp is not None:
                        await cursor.execute(f"RELEASE SAVEPOINT {current_sp}")
                    else:
                        if not skip_last_update:
                            await self._update_last_update_date(cursor)
                        await cursor.execute("COMMIT")

            finally:
                if self.savepoint_stack:
                    self.savepoint_stack.pop()
                await cursor.close()

    @asynccontextmanager
    async def read(self) -> AsyncGenerator[CapacitorDBCursor, None]:
        async with self._lock:
            cursor = self._cursor()
            try:
                yield cursor
            finally:
                await cursor.close()

    async def _update_last_update_date(self, cursor: CapacitorDBCursor):
        timestamp = datetime.now().astimezone().isoformat()
        await cursor.execute(
            "INSERT OR REPLACE INTO sys_config (key, value) VALUES (?, ?)",
            ("last_update", timestamp),
        )

    async def close(self):
        async with self._lock:
            if js is None:
                self._conn = None
                return

            try:
                await js.jsBridge.sqlite.closeDatabase()
            finally:
                self._conn = None

    async def silent_close(self) -> bool:
        try:
            await self.close()
            return True
        except Exception:
            return False

    async def wal_checkpoint(self, mode: str = "PASSIVE") -> None:
        async with self.read() as cursor:
            await cursor.execute(f"PRAGMA wal_checkpoint({mode})")

    def set_connection(self, connection: UnderlyingConnection | None) -> None:
        self._conn = connection
        self.savepoint_stack = []
