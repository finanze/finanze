import json
from http import HTTPStatus

from domain.entity import Feature
from domain.exception.exceptions import ExecutionConflict
from domain.export import NumberFormat
from domain.file_upload import FileUpload
from domain.global_position import ProductType
from domain.importing import ImportFileRequest
from domain.settings import TemplateConfig
from domain.use_cases.import_file import ImportFile
from quart import jsonify, request


async def import_file_route(import_file_uc: ImportFile):
    content_type = request.content_type
    if not content_type or "multipart/form-data" not in content_type:
        return (
            jsonify(
                {
                    "code": "INVALID_REQUEST",
                    "message": "Content type must be multipart/form-data",
                }
            ),
            HTTPStatus.BAD_REQUEST,
        )

    uploaded_file = (await request.files).get("file")
    if not uploaded_file:
        return (
            jsonify({"code": "INVALID_REQUEST", "message": "Missing file"}),
            HTTPStatus.BAD_REQUEST,
        )

    form = await request.form
    date_format = form.get("dateFormat")
    datetime_format = form.get("datetimeFormat")
    number_format_raw = form.get("numberFormat")
    feature_raw = form.get("feature")
    product_raw = form.get("product")
    template_id = form.get("templateId")
    template_params_raw = form.get("templateParams")

    if not all([feature_raw, product_raw, template_id]):
        return (
            jsonify({"code": "INVALID_REQUEST", "message": "Missing required fields"}),
            HTTPStatus.BAD_REQUEST,
        )

    try:
        feature = Feature(feature_raw)
    except ValueError:
        return (
            jsonify({"code": "INVALID_REQUEST", "message": "Invalid feature"}),
            HTTPStatus.BAD_REQUEST,
        )

    try:
        product = ProductType(product_raw)
    except ValueError:
        return (
            jsonify({"code": "INVALID_REQUEST", "message": "Invalid product"}),
            HTTPStatus.BAD_REQUEST,
        )

    try:
        number_format = NumberFormat(number_format_raw)
    except ValueError:
        return (
            jsonify({"code": "INVALID_REQUEST", "message": "Invalid number format"}),
            HTTPStatus.BAD_REQUEST,
        )

    template_params = None
    if template_params_raw:
        try:
            template_params = json.loads(template_params_raw)
            if not isinstance(template_params, dict):
                raise ValueError("templateParams must be an object")
        except ValueError as exc:
            return (
                jsonify(
                    {
                        "code": "INVALID_REQUEST",
                        "message": f"Invalid template params: {exc}",
                    }
                ),
                HTTPStatus.BAD_REQUEST,
            )

    file_upload = FileUpload(
        filename=uploaded_file.filename,
        content_type=uploaded_file.content_type,
        content_length=uploaded_file.content_length or 0,
        data=uploaded_file.stream,
    )

    preview_raw = request.args.get("preview")
    if preview_raw is None:
        preview = True
    else:
        pr = preview_raw.strip().lower()
        if pr == "true":
            preview = True
        elif pr == "false":
            preview = False
        else:
            return (
                jsonify(
                    {"code": "INVALID_REQUEST", "message": "Invalid preview value"}
                ),
                HTTPStatus.BAD_REQUEST,
            )

    request_model = ImportFileRequest(
        file=file_upload,
        number_format=number_format,
        feature=feature,
        product=product,
        datetime_format=datetime_format,
        date_format=date_format,
        template=TemplateConfig(id=template_id, params=template_params),
        preview=preview,
    )

    try:
        result = await import_file_uc.execute(request_model)
    except ExecutionConflict:
        return (
            jsonify(
                {"code": "EXECUTION_CONFLICT", "message": "Import already running"}
            ),
            HTTPStatus.CONFLICT,
        )

    response = {"code": result.code.name}
    if result.data:
        response["data"] = result.data
    if result.errors:
        response["errors"] = result.errors

    return jsonify(response), HTTPStatus.OK
