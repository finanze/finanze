from typing import Optional

from domain.ai import AIInputModality

MODALITY_TAGS = {
    "text": AIInputModality.TEXT,
    "image": AIInputModality.IMAGE,
    "file": AIInputModality.DOCUMENT,
    "document": AIInputModality.DOCUMENT,
    "pdf": AIInputModality.DOCUMENT,
}

OPENAI_TEXT_ONLY_PREFIXES = (
    "gpt-3.5",
    "gpt-4-0",
    "gpt-4-1",
    "gpt-4-32k",
    "gpt-4-turbo-preview",
    "gpt-oss",
    "o1-mini",
    "o1-preview",
    "o3-mini",
)
OPENAI_VISION_PREFIXES = (
    "gpt-4o",
    "chatgpt-4o",
    "gpt-4.1",
    "gpt-4.5",
    "gpt-4-turbo",
    "gpt-5",
    "gpt-6",
    "o1",
    "o3",
    "o4",
)
OPENAI_VISION = frozenset(
    {AIInputModality.TEXT, AIInputModality.IMAGE, AIInputModality.DOCUMENT}
)
TEXT_ONLY = frozenset({AIInputModality.TEXT})


def parse_input_modalities(raw) -> Optional[set[AIInputModality]]:
    if not isinstance(raw, list):
        return None
    modalities = {
        MODALITY_TAGS[tag.casefold()]
        for tag in raw
        if isinstance(tag, str) and tag.casefold() in MODALITY_TAGS
    }
    return modalities or None


def openai_input_modalities(model_id: str) -> Optional[set[AIInputModality]]:
    normalized = model_id.casefold()
    if normalized == "gpt-4" or normalized.startswith(OPENAI_TEXT_ONLY_PREFIXES):
        return set(TEXT_ONLY)
    if normalized.startswith(OPENAI_VISION_PREFIXES):
        return set(OPENAI_VISION)
    return None
