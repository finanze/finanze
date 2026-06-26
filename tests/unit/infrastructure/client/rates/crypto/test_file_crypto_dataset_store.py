import pytest

from infrastructure.client.rates.crypto.file_crypto_dataset_store import (
    FileCryptoDatasetStore,
)


class TestFileCryptoDatasetStore:
    @pytest.mark.asyncio
    async def test_save_and_load_roundtrip(self, tmp_path):
        store = FileCryptoDatasetStore(str(tmp_path))

        await store.save("cg", '{"hello": "world"}')
        assert await store.load("cg") == '{"hello": "world"}'
        assert (tmp_path / "coingecko.json").exists()

    @pytest.mark.asyncio
    async def test_load_missing_returns_none(self, tmp_path):
        store = FileCryptoDatasetStore(str(tmp_path))
        assert await store.load("cmc") is None

    @pytest.mark.asyncio
    async def test_unknown_key_is_ignored(self, tmp_path):
        store = FileCryptoDatasetStore(str(tmp_path))
        await store.save("unknown", "data")
        assert await store.load("unknown") is None
        assert not any(tmp_path.iterdir())

    @pytest.mark.asyncio
    async def test_cmc_key_uses_cmc_filename(self, tmp_path):
        store = FileCryptoDatasetStore(str(tmp_path))
        await store.save("cmc", "payload")
        assert (tmp_path / "cmc.json").exists()
        assert await store.load("cmc") == "payload"
