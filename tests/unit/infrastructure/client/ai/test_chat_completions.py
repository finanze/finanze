from domain.ai import (
    AIChoiceQuestion,
    AIDecisionRequest,
    AIGenerationRequest,
    AIGenerationStatus,
    AIJsonSchema,
    AIMessage,
    AIMessageRole,
)
from domain.dezimal import Dezimal
from infrastructure.client.ai.chat_completions import (
    chat_messages,
    decision_body,
    json_schema_format,
    parse_chat_completion,
    parse_decisions,
)


def _request(**kwargs) -> AIGenerationRequest:
    return AIGenerationRequest(
        model="gemma",
        messages=[AIMessage(role=AIMessageRole.USER, content="hello")],
        **kwargs,
    )


def _completion(message: dict, finish_reason: str = "stop", usage=None) -> dict:
    body = {"choices": [{"message": message, "finish_reason": finish_reason}]}
    if usage is not None:
        body["usage"] = usage
    return body


class TestChatMessages:
    def test_puts_instructions_first(self):
        assert chat_messages(_request(instructions="Be precise")) == [
            {"role": "system", "content": "Be precise"},
            {"role": "user", "content": "hello"},
        ]

    def test_without_instructions(self):
        assert chat_messages(_request()) == [{"role": "user", "content": "hello"}]


def test_json_schema_format():
    schema = AIJsonSchema(name="results", schema={"type": "object"})
    assert json_schema_format(schema) == {
        "type": "json_schema",
        "json_schema": {
            "name": "results",
            "strict": True,
            "schema": {"type": "object"},
        },
    }


class TestParseChatCompletion:
    def test_completed_with_usage(self):
        generation = parse_chat_completion(
            _completion(
                {"role": "assistant", "content": '{"results": []}'},
                usage={"prompt_tokens": 10, "completion_tokens": 3},
            )
        )
        assert generation.status == AIGenerationStatus.COMPLETED
        assert generation.text == '{"results": []}'
        assert generation.usage.input_tokens == 10
        assert generation.usage.output_tokens == 3

    def test_joins_list_content(self):
        generation = parse_chat_completion(
            _completion(
                {"content": [{"type": "text", "text": "a"}, {"text": "b"}, "x"]}
            )
        )
        assert generation.text == "ab"
        assert generation.usage is None

    def test_refusal(self):
        generation = parse_chat_completion(
            _completion({"content": None, "refusal": "No"})
        )
        assert generation.status == AIGenerationStatus.REFUSED
        assert generation.refusal == "No"
        assert generation.text is None

    def test_truncated(self):
        generation = parse_chat_completion(
            _completion({"content": '{"res'}, finish_reason="length")
        )
        assert generation.status == AIGenerationStatus.INCOMPLETE

    def test_empty_response(self):
        generation = parse_chat_completion({})
        assert generation.status == AIGenerationStatus.COMPLETED
        assert generation.text is None


class TestDecisions:
    def test_decision_body(self):
        request = AIDecisionRequest(
            model="laya",
            state={"categories": {"food": "Food"}},
            questions=[
                AIChoiceQuestion(id="m1", instructions="Pick", options=["food", "none"])
            ],
        )
        assert decision_body(request) == {
            "model": "laya",
            "state": {"categories": {"food": "Food"}},
            "questions": {
                "m1": {
                    "type": "choice",
                    "instructions": "Pick",
                    "criteria": {"food": None, "none": None},
                }
            },
        }

    def test_parse_decisions_skips_invalid_values(self):
        result = parse_decisions(
            {
                "answers": {
                    "m1": {
                        "choice": "food",
                        "confidence": 0.8,
                        "probabilities": {"food": 0.8, "none": "bad"},
                    },
                    "m2": "invalid",
                }
            }
        )
        assert list(result.answers) == ["m1"]
        answer = result.answers["m1"]
        assert answer.choice == "food"
        assert answer.confidence == Dezimal("0.8")
        assert answer.probabilities == {"food": Dezimal("0.8")}

    def test_parse_decisions_without_answers(self):
        assert parse_decisions({}).answers == {}
