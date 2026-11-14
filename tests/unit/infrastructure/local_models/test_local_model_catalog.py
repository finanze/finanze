from domain.local_model import (
    HUGGING_FACE_REPO_PATTERN,
    QUANT_TAG_PATTERN,
    hugging_face_model_id,
)
from infrastructure.local_models.local_model_catalog import StaticLocalModelCatalog


class TestStaticLocalModelCatalog:
    def test_entries_are_valid(self):
        entries = StaticLocalModelCatalog().entries()
        assert entries
        assert len({entry.id for entry in entries}) == len(entries)
        for entry in entries:
            assert HUGGING_FACE_REPO_PATTERN.match(entry.repo)
            assert QUANT_TAG_PATTERN.match(entry.quant)
            assert entry.id == hugging_face_model_id(entry.repo, entry.quant)
            assert entry.size > 0
            assert entry.ram > entry.size
            assert (entry.vision_size is None) == (entry.vision_ram is None)
            if entry.vision_ram is not None:
                assert entry.vision_ram > entry.vision_size

    def test_vision_entries(self):
        entries = {e.name: e for e in StaticLocalModelCatalog().entries()}
        assert entries["Qwen3.5 0.8B"].vision_size == 207346528
        assert entries["Granite 4.0 Micro"].vision_size is None
        assert sum(1 for e in entries.values() if e.vision_size) == 8

    def test_find_is_case_insensitive(self):
        catalog = StaticLocalModelCatalog()
        entry = catalog.entries()[0]
        assert catalog.find(entry.id.upper()) == entry
        assert catalog.find("unknown/repo:Q4_K_M") is None

    def test_entries_are_copied(self):
        catalog = StaticLocalModelCatalog()
        catalog.entries().clear()
        assert catalog.entries()
