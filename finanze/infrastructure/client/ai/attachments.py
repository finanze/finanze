import base64

from domain.ai import AIAttachment, AIMessage

DEFAULT_DOCUMENT_NAME = "document.pdf"


def encode_attachment(attachment: AIAttachment) -> str:
    return base64.b64encode(attachment.data).decode("ascii")


def data_uri(attachment: AIAttachment) -> str:
    return f"data:{attachment.mime_type};base64,{encode_attachment(attachment)}"


def is_image(attachment: AIAttachment) -> bool:
    return attachment.mime_type.startswith("image/")


def chat_content(message: AIMessage):
    if not message.attachments:
        return message.content
    parts = [{"type": "text", "text": message.content}] if message.content else []
    for attachment in message.attachments:
        if is_image(attachment):
            parts.append(
                {
                    "type": "image_url",
                    "image_url": {"url": data_uri(attachment), "detail": "high"},
                }
            )
        else:
            parts.append(
                {
                    "type": "file",
                    "file": {
                        "filename": attachment.name or DEFAULT_DOCUMENT_NAME,
                        "file_data": data_uri(attachment),
                    },
                }
            )
    return parts


def responses_content(message: AIMessage):
    if not message.attachments:
        return message.content
    parts = [{"type": "input_text", "text": message.content}] if message.content else []
    for attachment in message.attachments:
        if is_image(attachment):
            parts.append(
                {
                    "type": "input_image",
                    "image_url": data_uri(attachment),
                    "detail": "high",
                }
            )
        else:
            parts.append(
                {
                    "type": "input_file",
                    "filename": attachment.name or DEFAULT_DOCUMENT_NAME,
                    "file_data": data_uri(attachment),
                }
            )
    return parts


def responses_input(messages: list[AIMessage]) -> list[dict]:
    return [
        {"role": message.role.value.lower(), "content": responses_content(message)}
        for message in messages
    ]
