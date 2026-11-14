import pytest
from domain.local_model import find_mmproj_sibling, model_id_repo


class TestFindMmprojSibling:
    def test_closest_quant_bits(self):
        paths = [
            "mmproj-F32.gguf",
            "mmproj-Q8_0.gguf",
            "mmproj-F16.gguf",
            "model-Q4_K_M.gguf",
        ]
        assert find_mmproj_sibling(paths, "model-Q4_K_M.gguf") == "mmproj-Q8_0.gguf"
        assert find_mmproj_sibling(paths, "model-BF16.gguf") == "mmproj-F16.gguf"

    def test_first_wins_ties(self):
        paths = ["mmproj-BF16.gguf", "mmproj-F16.gguf"]
        assert find_mmproj_sibling(paths, "model-Q4_K_M.gguf") == "mmproj-BF16.gguf"

    def test_deepest_shared_folder_wins(self):
        paths = ["mmproj-Q8_0.gguf", "sub/mmproj-F16.gguf", "other/mmproj-Q4_0.gguf"]
        assert find_mmproj_sibling(paths, "sub/model-Q4_K_M.gguf") == (
            "sub/mmproj-F16.gguf"
        )
        assert find_mmproj_sibling(paths, "deep/x/model-Q4_K_M.gguf") == (
            "mmproj-Q8_0.gguf"
        )

    def test_ignores_deeper_folders_and_non_gguf(self):
        paths = ["sub/mmproj-F16.gguf", "mmproj-notes.txt", "MMPROJ-F16.gguf"]
        assert find_mmproj_sibling(paths, "model-Q4_K_M.gguf") is None

    def test_split_and_named_projectors(self):
        paths = [
            "Ministral-3-3B-Instruct-2512-BF16-mmproj.gguf",
            "model-Q4_K_M-00001-of-00002.gguf",
        ]
        assert find_mmproj_sibling(paths, "model-Q4_K_M-00001-of-00002.gguf") == (
            "Ministral-3-3B-Instruct-2512-BF16-mmproj.gguf"
        )

    def test_none_without_projectors(self):
        assert find_mmproj_sibling(["model-Q4_K_M.gguf"], "model-Q4_K_M.gguf") is None


class TestModelIdRepo:
    @pytest.mark.parametrize(
        "model_id, repo",
        [
            ("org/model-GGUF:Q4_K_M", "org/model-GGUF"),
            ("local/mine", ""),
            ("server-model", ""),
        ],
    )
    def test_repo(self, model_id, repo):
        assert model_id_repo(model_id) == repo
