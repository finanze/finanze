import asyncio

import pytest
from infrastructure.agent_runtime.runtime_pool import AgentRuntimePool

PROVIDER = "provider"


class FakeRuntime:
    def __init__(self, name: str, fail_stop: bool = False):
        self.name = name
        self.fail_stop = fail_stop
        self.stopped = 0

    async def stop(self):
        self.stopped += 1
        if self.fail_stop:
            raise RuntimeError("stop failed")


class Factory:
    def __init__(self, delay: float = 0, error: Exception | None = None):
        self.delay = delay
        self.error = error
        self.created: list[FakeRuntime] = []

    async def __call__(self) -> FakeRuntime:
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error:
            raise self.error
        runtime = FakeRuntime(f"runtime-{len(self.created)}")
        self.created.append(runtime)
        return runtime


async def _use(pool: AgentRuntimePool, factory: Factory, secret: str = "secret"):
    async with pool.use(PROVIDER, secret, factory) as runtime:
        return runtime


@pytest.mark.asyncio
async def test_reuses_instance_for_same_secret():
    pool = AgentRuntimePool()
    factory = Factory()

    first = await _use(pool, factory)
    second = await _use(pool, factory)

    assert first is second
    assert len(factory.created) == 1
    assert first.stopped == 0
    await pool.release_all()


@pytest.mark.asyncio
async def test_concurrent_first_use_starts_once():
    pool = AgentRuntimePool()
    factory = Factory(delay=0.01)

    runtimes = await asyncio.gather(*(_use(pool, factory) for _ in range(5)))

    assert len(factory.created) == 1
    assert all(runtime is runtimes[0] for runtime in runtimes)
    await pool.release_all()


@pytest.mark.asyncio
async def test_different_secret_replaces_idle_instance():
    pool = AgentRuntimePool()
    factory = Factory()

    first = await _use(pool, factory, "first")
    second = await _use(pool, factory, "second")

    assert first is not second
    assert first.stopped == 1
    assert second.stopped == 0
    await pool.release_all()


@pytest.mark.asyncio
async def test_replaced_instance_stops_after_current_use():
    pool = AgentRuntimePool()
    factory = Factory()

    async with pool.use(PROVIDER, "first", factory) as first:
        second = await _use(pool, factory, "second")
        assert first.stopped == 0

    assert first.stopped == 1
    assert second.stopped == 0
    await pool.release_all()


@pytest.mark.asyncio
async def test_idle_instance_expires_but_in_use_one_does_not():
    pool = AgentRuntimePool(idle_seconds=0.01)
    factory = Factory()

    async with pool.use(PROVIDER, "secret", factory) as runtime:
        await asyncio.sleep(0.03)
        assert runtime.stopped == 0

    await asyncio.sleep(0.03)

    assert runtime.stopped == 1
    replacement = await _use(pool, factory)
    assert replacement is not runtime
    await pool.release_all()


@pytest.mark.asyncio
async def test_reuse_cancels_idle_expiry():
    pool = AgentRuntimePool(idle_seconds=0.02)
    factory = Factory()

    runtime = await _use(pool, factory)
    await asyncio.sleep(0.01)
    async with pool.use(PROVIDER, "secret", factory):
        await asyncio.sleep(0.03)

    assert runtime.stopped == 0
    await pool.release_all()
    assert runtime.stopped == 1


@pytest.mark.asyncio
async def test_discard_only_matches_same_secret():
    pool = AgentRuntimePool()
    factory = Factory()
    runtime = await _use(pool, factory)

    await pool.discard(PROVIDER, "other")
    assert runtime.stopped == 0

    await pool.discard(PROVIDER, "secret")
    assert runtime.stopped == 1
    assert await _use(pool, factory) is not runtime
    await pool.release_all()


@pytest.mark.asyncio
async def test_invalidate_and_release_all_stop_instances():
    pool = AgentRuntimePool()
    factory = Factory()
    first = await _use(pool, factory)
    async with pool.use("other", "secret", factory) as second:
        pass

    await pool.invalidate(PROVIDER)
    assert first.stopped == 1
    assert second.stopped == 0

    await pool.release_all()
    assert second.stopped == 1


@pytest.mark.asyncio
async def test_failed_start_is_not_cached():
    pool = AgentRuntimePool()

    with pytest.raises(OSError):
        await _use(pool, Factory(error=OSError("spawn failed")))

    factory = Factory()
    assert await _use(pool, factory) is factory.created[0]
    await pool.release_all()


@pytest.mark.asyncio
async def test_stop_errors_are_swallowed():
    pool = AgentRuntimePool()

    async def factory():
        return FakeRuntime("broken", fail_stop=True)

    runtime = await _use(pool, factory)
    await pool.release_all()

    assert runtime.stopped == 1


@pytest.mark.asyncio
async def test_concurrency_is_limited_per_instance():
    pool = AgentRuntimePool(max_concurrency=1)
    factory = Factory()
    active = 0
    peak = 0

    async def call():
        nonlocal active, peak
        async with pool.use(PROVIDER, "secret", factory):
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.01)
            active -= 1

    await asyncio.gather(*(call() for _ in range(3)))

    assert peak == 1
    await pool.release_all()


def test_fingerprint_does_not_expose_secret():
    fingerprint = AgentRuntimePool.fingerprint("gho_secret")
    assert "gho_secret" not in fingerprint
    assert fingerprint == AgentRuntimePool.fingerprint("gho_secret")
    assert fingerprint != AgentRuntimePool.fingerprint("gho_other")
