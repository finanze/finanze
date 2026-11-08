import asyncio
import hashlib
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import AsyncIterator, Awaitable, Callable, Optional, Protocol, TypeVar

from application.ports.agent_runtime_port import AgentRuntimePort

DEFAULT_IDLE_SECONDS = 300
DEFAULT_MAX_CONCURRENCY = 2


class AgentRuntime(Protocol):
    async def stop(self) -> None: ...


R = TypeVar("R", bound=AgentRuntime)


@dataclass(eq=False)
class _Instance:
    key: str
    runtime: AgentRuntime
    semaphore: asyncio.Semaphore
    in_use: int = 0
    retired: bool = False
    idle_task: Optional[asyncio.Task] = field(default=None)


class AgentRuntimePool(AgentRuntimePort):
    def __init__(
        self,
        idle_seconds: float = DEFAULT_IDLE_SECONDS,
        max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
    ):
        self._idle_seconds = idle_seconds
        self._max_concurrency = max_concurrency
        self._instances: dict[str, _Instance] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._log = logging.getLogger(__name__)

    @staticmethod
    def fingerprint(secret: str) -> str:
        return hashlib.sha256(secret.encode("utf-8")).hexdigest()

    @asynccontextmanager
    async def use(
        self, provider: str, secret: str, factory: Callable[[], Awaitable[R]]
    ) -> AsyncIterator[R]:
        instance = await self._acquire(provider, self.fingerprint(secret), factory)
        try:
            async with instance.semaphore:
                yield instance.runtime
        finally:
            await self._release(provider, instance)

    async def discard(self, provider: str, secret: str):
        key = self.fingerprint(secret)
        async with self._lock(provider):
            instance = self._instances.get(provider)
            if instance is None or instance.key != key:
                return
            del self._instances[provider]
        await self._retire(instance)

    async def invalidate(self, provider: str):
        async with self._lock(provider):
            instance = self._instances.pop(provider, None)
        if instance is not None:
            await self._retire(instance)

    async def release_all(self):
        for provider in list(self._instances):
            await self.invalidate(provider)

    def _lock(self, provider: str) -> asyncio.Lock:
        lock = self._locks.get(provider)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[provider] = lock
        return lock

    async def _acquire(
        self, provider: str, key: str, factory: Callable[[], Awaitable[R]]
    ) -> _Instance:
        async with self._lock(provider):
            current = self._instances.get(provider)
            if current is not None and current.key == key:
                self._cancel_idle(current)
                current.in_use += 1
                return current

            if current is not None:
                del self._instances[provider]
                await self._retire(current)

            runtime = await factory()
            instance = _Instance(
                key=key,
                runtime=runtime,
                semaphore=asyncio.Semaphore(self._max_concurrency),
                in_use=1,
            )
            self._instances[provider] = instance
            return instance

    async def _release(self, provider: str, instance: _Instance):
        async with self._lock(provider):
            instance.in_use -= 1
            if instance.in_use > 0:
                return
            if not instance.retired:
                instance.idle_task = asyncio.create_task(
                    self._expire(provider, instance)
                )
                return
        await self._stop(instance)

    async def _expire(self, provider: str, instance: _Instance):
        await asyncio.sleep(self._idle_seconds)
        async with self._lock(provider):
            if self._instances.get(provider) is not instance or instance.in_use > 0:
                return
            del self._instances[provider]
            instance.idle_task = None
        await self._stop(instance)

    async def _retire(self, instance: _Instance):
        instance.retired = True
        self._cancel_idle(instance)
        if instance.in_use == 0:
            await self._stop(instance)

    def _cancel_idle(self, instance: _Instance):
        if instance.idle_task is not None:
            if instance.idle_task is not asyncio.current_task():
                instance.idle_task.cancel()
            instance.idle_task = None

    async def _stop(self, instance: _Instance):
        try:
            await instance.runtime.stop()
        except Exception:
            self._log.warning("Could not stop agent runtime", exc_info=True)
