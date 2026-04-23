from http import HTTPStatus
from io import BytesIO

from domain.entity import Feature
from domain.export import FileExportRequest, FileFormat, NumberFormat
from domain.global_position import ProductType
from domain.settings import TemplateConfig
from domain.use_cases.export_file import ExportFile
from quart import jsonify, request, send_file


async def export_file(export_file_uc: ExportFile):
    body = await request.get_json(silent=True) or {}

    raw_format = body.get("format")
    raw_feature = body.get("feature")
    raw_number_format = body.get("number_format")

    if not raw_format:
        return (
            jsonify({"code": "INVALID_REQUEST", "message": "Missing format"}),
            HTTPStatus.BAD_REQUEST,
        )
    if not raw_feature:
        return (
            jsonify({"code": "INVALID_REQUEST", "message": "Missing feature"}),
            HTTPStatus.BAD_REQUEST,
        )

    try:
        export_format = FileFormat(raw_format)
    except ValueError:
        return (
            jsonify({"code": "INVALID_REQUEST", "message": "Invalid format"}),
            HTTPStatus.BAD_REQUEST,
        )

    try:
        feature = Feature(raw_feature)
    except ValueError:
        return (
            jsonify({"code": "INVALID_REQUEST", "message": "Invalid feature"}),
            HTTPStatus.BAD_REQUEST,
        )

    try:
        number_format = NumberFormat(raw_number_format)
    except ValueError:
        return (
            jsonify({"code": "INVALID_REQUEST", "message": "Invalid number format"}),
            HTTPStatus.BAD_REQUEST,
        )

    raw_products = body.get("data") or []
    products = []
    if raw_products:
        if feature == Feature.AUTO_CONTRIBUTIONS:
            return (
                jsonify(
                    {
                        "code": "INVALID_REQUEST",
                        "message": "Products not applicable for AUTO_CONTRIBUTIONS",
                    }
                ),
                HTTPStatus.BAD_REQUEST,
            )
        for raw in raw_products:
            try:
                products.append(ProductType(raw))
            except ValueError:
                return (
                    jsonify(
                        {
                            "code": "INVALID_REQUEST",
                            "message": f"Invalid product type: {raw}",
                        }
                    ),
                    HTTPStatus.BAD_REQUEST,
                )

    datetime_format = body.get("datetime_format")
    date_format = body.get("date_format")

    raw_template = body.get("template")
    template_config = None
    if raw_template and isinstance(raw_template, dict) and raw_template.get("id"):
        template_config = TemplateConfig(
            id=raw_template["id"], params=raw_template.get("params")
        )

    file_request = FileExportRequest(
        format=export_format,
        number_format=number_format,
        feature=feature,
        data=products or None,
        datetime_format=datetime_format,
        date_format=date_format,
        template=template_config,
    )

    result = await export_file_uc.execute(file_request)

    response = await send_file(
        BytesIO(result.data),
        mimetype=result.content_type,
        as_attachment=True,
        attachment_filename=result.filename,
    )
    response.headers["Content-Length"] = str(result.size)
    return response
