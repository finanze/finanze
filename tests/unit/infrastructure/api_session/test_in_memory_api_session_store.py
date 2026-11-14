from infrastructure.api_session.in_memory_api_session_store import (
    InMemoryApiSessionStore,
)


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
