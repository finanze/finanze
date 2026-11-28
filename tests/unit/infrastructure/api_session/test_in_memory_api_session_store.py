from datetime import timedelta

from infrastructure.api_session import in_memory_api_session_store
from infrastructure.api_session.in_memory_api_session_store import (
    InMemoryApiSessionStore,
)


def _advance(monkeypatch, delta):
    now = in_memory_api_session_store._now() + delta
    monkeypatch.setattr(in_memory_api_session_store, "_now", lambda: now)


class TestInMemoryApiSessionStore:
    def test_created_tokens_are_unique_and_valid(self):
        store = InMemoryApiSessionStore()

        first = store.create()
        second = store.create()

        assert first != second
        assert len(first) >= 40
        assert store.is_valid(first)
        assert store.is_valid(second)

    def test_unknown_or_empty_tokens_are_invalid(self):
        store = InMemoryApiSessionStore()
        store.create()

        assert not store.is_valid(None)
        assert not store.is_valid("")
        assert not store.is_valid("unknown")

    def test_raw_tokens_are_not_stored(self):
        store = InMemoryApiSessionStore()
        token = store.create()

        assert token not in store._digests

    def test_revoke_all_invalidates_every_token(self):
        store = InMemoryApiSessionStore()
        tokens = [store.create() for _ in range(3)]

        store.revoke_all()

        assert not any(store.is_valid(token) for token in tokens)

    def test_remembered_tokens_never_expire_without_ttl(self, monkeypatch):
        store = InMemoryApiSessionStore()
        token = store.create(remember=True)

        _advance(monkeypatch, timedelta(days=3650))

        assert store.is_valid(token)

    def test_remembered_tokens_expire_after_ttl(self, monkeypatch):
        store = InMemoryApiSessionStore(remember_ttl=timedelta(days=30))
        remembered = store.create(remember=True)
        transient = store.create()

        _advance(monkeypatch, timedelta(days=29))
        assert store.is_valid(remembered)

        _advance(monkeypatch, timedelta(days=2))
        assert not store.is_valid(remembered)
        assert store.is_valid(transient)
        assert len(store._digests) == 1
