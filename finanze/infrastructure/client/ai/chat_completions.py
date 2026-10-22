from domain.ai import (
    AIDecisionAnswer,
    AIDecisionRequest,
    AIDecisionResult,
    AIGeneration,
    AIGenerationRequest,
    AIGenerationStatus,
    AIJsonSchema,
    AIUsage,
)
from infrastructure.client.ai.http_ai_client import to_dezimal


def chat_messages(request: AIGenerationRequest) -> list[dict]:
    messages = []
    if request.instructions:
        messages.append({"role": "system", "content": request.instructions})
    messages += [
        {"role": message.role.value.lower(), "content": message.content}
        for message in request.messages
    ]
    return messages


def json_schema_format(schema: AIJsonSchema) -> dict:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": schema.name,
            "strict": True,
            "schema": schema.schema,
        },
    }


def parse_chat_completion(response: dict) -> AIGeneration:
    choices = response.get("choices") or []
    choice = choices[0] if choices else {}
    message = choice.get("message") or {}
    usage = response.get("usage") or {}
    content = message.get("content")
    if isinstance(content, list):
        content = "".join(
            part.get("text", "") for part in content if isinstance(part, dict)
        )
    if message.get("refusal"):
        generation_status = AIGenerationStatus.REFUSED
    elif choice.get("finish_reason") == "length":
        generation_status = AIGenerationStatus.INCOMPLETE
    else:
        generation_status = AIGenerationStatus.COMPLETED
    return AIGeneration(
        status=generation_status,
        text=content or None,
        refusal=message.get("refusal"),
        usage=AIUsage(
            input_tokens=usage.get("prompt_tokens") or 0,
            output_tokens=usage.get("completion_tokens") or 0,
        )
        if usage
        else None,
    )


def decision_body(request: AIDecisionRequest) -> dict:
    return {
        "model": request.model,
        "state": request.state,
        "questions": {
            question.id: {
                "type": "choice",
                "instructions": question.instructions,
                "criteria": dict.fromkeys(question.options),
            }
            for question in request.questions
        },
    }


def parse_decisions(response: dict) -> AIDecisionResult:
    answers = {}
    for question_id, answer in (response.get("answers") or {}).items():
        if not isinstance(answer, dict):
            continue
        probabilities = {
            option: probability
            for option, value in (answer.get("probabilities") or {}).items()
            if (probability := to_dezimal(value)) is not None
        }
        answers[question_id] = AIDecisionAnswer(
            choice=answer.get("choice"),
            confidence=to_dezimal(answer.get("confidence")),
            probabilities=probabilities,
        )
    return AIDecisionResult(answers=answers)
