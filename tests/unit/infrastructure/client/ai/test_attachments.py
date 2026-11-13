import json

from domain.ai import AIAttachment, AIGenerationRequest, AIMessage, AIMessageRole
from infrastructure.client.ai.attachments import chat_content, responses_input
from infrastructure.client.ai.chat_completions import chat_messages
from infrastructure.client.ai.claude_agent.claude_cli_runtime import _stdin_payload

IMAGE = AIAttachment(mime_type="image/png", data=b"png")
PDF = AIAttachment(mime_type="application/pdf", data=b"pdf", name="s.pdf")


def _message(*attachments):
    return AIMessage(
        role=AIMessageRole.USER, content="Extract", attachments=list(attachments)
    )


def test_plain_messages_keep_string_content():
    request = AIGenerationRequest(model="m", messages=[_message()])
    assert chat_messages(request) == [{"role": "user", "content": "Extract"}]
    assert responses_input([_message()]) == [{"role": "user", "content": "Extract"}]


def test_chat_content_parts():
    assert chat_content(_message(IMAGE, PDF)) == [
        {"type": "text", "text": "Extract"},
        {
            "type": "image_url",
            "image_url": {"url": "data:image/png;base64,cG5n", "detail": "high"},
        },
        {
            "type": "file",
            "file": {
                "filename": "s.pdf",
                "file_data": "data:application/pdf;base64,cGRm",
            },
        },
    ]


def test_responses_content_parts():
    content = responses_input([_message(IMAGE, PDF)])[0]["content"]
    assert content == [
        {"type": "input_text", "text": "Extract"},
        {
            "type": "input_image",
            "image_url": "data:image/png;base64,cG5n",
            "detail": "high",
        },
        {
            "type": "input_file",
            "filename": "s.pdf",
            "file_data": "data:application/pdf;base64,cGRm",
        },
    ]


def test_claude_stdin_is_plain_without_attachments():
    assert _stdin_payload("hello", None) == b"hello"


def test_claude_stdin_is_stream_json_with_attachments():
    block = {"type": "image", "source": {"type": "base64", "data": "x"}}
    payload = _stdin_payload("hello", [block])
    assert payload.endswith(b"\n")
    message = json.loads(payload)
    assert message["type"] == "user"
    assert message["message"]["content"] == [{"type": "text", "text": "hello"}, block]
