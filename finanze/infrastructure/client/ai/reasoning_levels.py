from typing import Optional, Sequence

from domain.ai import AIReasoningEffort

REASONING_LEVEL_ORDER = ("low", "medium", "high", "xhigh", "max")
REASONING_LEVELS = {
    AIReasoningEffort.NONE: "low",
    AIReasoningEffort.LOW: "low",
    AIReasoningEffort.MEDIUM: "medium",
    AIReasoningEffort.HIGH: "high",
    AIReasoningEffort.EXTRA_HIGH: "xhigh",
}


def pick_reasoning_level(
    supported: Sequence[str], requested: Optional[AIReasoningEffort]
) -> Optional[str]:
    if not supported:
        return None
    preferred = REASONING_LEVELS.get(requested) if requested else None
    if preferred in supported:
        return preferred
    return next(
        (level for level in REASONING_LEVEL_ORDER if level in supported),
        None,
    )
