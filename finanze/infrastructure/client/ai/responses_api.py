import json

from domain.ai import AIGeneration, AIGenerationStatus, AIUsage


def parse_response_output(response: dict) -> AIGeneration:
    texts, refusals = [], []
    for item in response.get("output") or []:
        if item.get("type") != "message":
            continue
        for part in item.get("content") or []:
            if part.get("type") == "output_text":
                texts.append(part.get("text") or "")
            elif part.get("type") == "refusal":
                refusals.append(part.get("refusal") or "")

    if refusals:
        generation_status = AIGenerationStatus.REFUSED
    elif response.get("status") == "incomplete":
        generation_status = AIGenerationStatus.INCOMPLETE
    else:
        generation_status = AIGenerationStatus.COMPLETED
    usage = response.get("usage") or {}
    return AIGeneration(
        status=generation_status,
        text="".join(texts) or None,
        refusal="".join(refusals) or None,
        usage=AIUsage(
            input_tokens=usage.get("input_tokens") or 0,
            output_tokens=usage.get("output_tokens") or 0,
        )
        if usage
        else None,
    )


def parse_stream_events(body: str) -> list[dict]:
    events = []
    data_lines: list[str] = []

    def flush():
        data = "\n".join(data_lines)
        data_lines.clear()
        if not data or data == "[DONE]":
            return
        try:
            event = json.loads(data)
        except ValueError:
            return
        if isinstance(event, dict):
            events.append(event)

    for line in body.splitlines():
        if not line.strip():
            flush()
        elif line.startswith("data:"):
            value = line[5:]
            data_lines.append(value[1:] if value.startswith(" ") else value)
    flush()
    return events
