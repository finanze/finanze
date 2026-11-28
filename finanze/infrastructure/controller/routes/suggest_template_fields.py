from http import HTTPStatus

from domain.entity import Feature
from domain.exception.exceptions import (
    FeatureNotSupported,
    NoTableFound,
    PdfNoTextLayer,
    UnsupportedFileFormat,
)
from domain.file_upload import FileUpload
from domain.global_position import ProductType
from domain.importing import TemplateFieldsSuggestionRequest
from domain.use_cases.suggest_template_fields import SuggestTemplateFields
from quart import jsonify, request


def _invalid_request(message: str):
    return (
        jsonify({"code": "INVALID_REQUEST", "message": message}),
        HTTPStatus.BAD_REQUEST,
    )


async def suggest_template_fields(suggest_template_fields_uc: SuggestTemplateFields):
    content_type = request.content_type
    if not content_type or "multipart/form-data" not in content_type:
        return _invalid_request("Content type must be multipart/form-data")

    uploaded_file = (await request.files).get("file")
    if not uploaded_file:
        return _invalid_request("Missing file")

    form = await request.form
    try:
        feature = Feature(form.get("feature"))
        product = ProductType(form.get("product"))
    except ValueError:
        return _invalid_request("Invalid feature or product")

    file_upload = FileUpload(
        filename=uploaded_file.filename,
        content_type=uploaded_file.content_type,
        content_length=uploaded_file.content_length or 0,
        data=uploaded_file.stream,
    )

    try:
        suggestion = await suggest_template_fields_uc.execute(
            TemplateFieldsSuggestionRequest(
                file=file_upload, feature=feature, product=product
            )
        )
    except FeatureNotSupported:
        return _invalid_request("Unsupported feature or product")
    except PdfNoTextLayer:
        return (
            jsonify(
                {
                    "code": "PDF_NO_TEXT_LAYER",
                    "message": "PDF file has no selectable text",
                }
            ),
            HTTPStatus.BAD_REQUEST,
        )
    except NoTableFound:
        return (
            jsonify(
                {
                    "code": "NO_TABLE_FOUND",
                    "message": "No table found in file",
                }
            ),
            HTTPStatus.BAD_REQUEST,
        )
    except UnsupportedFileFormat:
        return (
            jsonify({"code": "UNSUPPORTED_FILE_FORMAT", "message": "Unsupported file"}),
            HTTPStatus.BAD_REQUEST,
        )

    return (
        jsonify(
            {
                "headers": suggestion.headers,
                "fields": [
                    {"field": field.field, "name": field.name}
                    for field in suggestion.fields
                ],
                "number_format": suggestion.number_format.value
                if suggestion.number_format
                else None,
                "date_format": suggestion.date_format,
                "detected_currency": suggestion.detected_currency,
                "missing_required_fields": suggestion.missing_required_fields,
                "matching_templates": [
                    str(template_id) for template_id in suggestion.matching_templates
                ],
            }
        ),
        HTTPStatus.OK,
    )
