from application.ports.local_model_catalog import LocalModelCatalog
from domain.local_model import LocalModelCatalogEntry

MB = 1_000_000


def _entry(
    repo: str,
    quant: str,
    name: str,
    size: int,
    ram: int,
    params: str,
    license: str,
    decisions: bool = False,
    languages: list[str] | None = None,
) -> LocalModelCatalogEntry:
    return LocalModelCatalogEntry(
        id=f"{repo}:{quant}",
        name=name,
        repo=repo,
        quant=quant,
        size=size,
        ram=ram,
        params=params,
        license=license,
        decisions=decisions,
        languages=languages,
    )


LOCAL_MODEL_CATALOG = [
    _entry(
        "unsloth/Qwen3.5-2B-GGUF",
        "Q4_K_M",
        "Qwen3.5 2B",
        1280835840,
        1600 * MB,
        "2B",
        "apache-2.0",
        languages=["multilingual"],
    ),
    _entry(
        "ibm-granite/granite-4.0-micro-GGUF",
        "Q4_K_M",
        "Granite 4.0 Micro",
        2099502528,
        3000 * MB,
        "3B",
        "apache-2.0",
        languages=["multilingual"],
    ),
    _entry(
        "mistralai/Ministral-3-3B-Instruct-2512-GGUF",
        "Q4_K_M",
        "Ministral 3 3B",
        2147023008,
        3200 * MB,
        "3B",
        "apache-2.0",
        languages=["multilingual"],
    ),
    _entry(
        "ggml-org/gemma-3-4b-it-GGUF",
        "Q4_K_M",
        "Gemma 3 4B",
        2489757856,
        3400 * MB,
        "4B",
        "gemma",
        languages=["multilingual"],
    ),
    _entry(
        "unsloth/Qwen3-4B-Instruct-2507-GGUF",
        "Q4_K_M",
        "Qwen3 4B Instruct 2507",
        2497281120,
        3700 * MB,
        "4B",
        "apache-2.0",
        languages=["multilingual"],
    ),
    _entry(
        "unsloth/gemma-4-E2B-it-GGUF",
        "Q4_K_M",
        "Gemma 4 E2B",
        3106738272,
        3300 * MB,
        "2B",
        "apache-2.0",
        languages=["multilingual"],
    ),
    _entry(
        "unsloth/gemma-4-E4B-it-GGUF",
        "Q4_K_M",
        "Gemma 4 E4B",
        4977171584,
        5400 * MB,
        "4B",
        "apache-2.0",
        languages=["multilingual"],
    ),
    _entry(
        "mistralai/Ministral-3-8B-Instruct-2512-GGUF",
        "Q4_K_M",
        "Ministral 3 8B",
        5198911904,
        6500 * MB,
        "8B",
        "apache-2.0",
        languages=["multilingual"],
    ),
    _entry(
        "unsloth/Qwen3.5-9B-GGUF",
        "Q4_K_M",
        "Qwen3.5 9B",
        5680522464,
        6200 * MB,
        "9B",
        "apache-2.0",
        languages=["multilingual"],
    ),
]


class StaticLocalModelCatalog(LocalModelCatalog):
    def entries(self) -> list[LocalModelCatalogEntry]:
        return list(LOCAL_MODEL_CATALOG)
