import json

from domain.exception.exceptions import FlowNotFound
from domain.file_upload import FileUpload
from domain.real_estate import CreateRealEstateRequest
from domain.use_cases.create_real_estate import CreateRealEstate
from quart import jsonify, request
from infrastructure.controller.mappers.real_estate_mapper import map_real_estate


async def create_real_estate(create_real_estate_uc: CreateRealEstate):
    try:
        file_upload = None
        content_type = request.content_type
        if content_type and "multipart/form-data" in content_type:
            form = await request.form
            if "data" not in form:
                return jsonify(
                    {
                        "code": "INVALID_REQUEST",
                        "message": "Missing 'data' field in form",
                    }
                ), 400

            try:
                body = json.loads(form["data"])
            except json.JSONDecodeError as e:
                return jsonify(
                    {
                        "code": "INVALID_REQUEST",
                        "message": f"Invalid JSON in 'data' field: {str(e)}",
                    }
                ), 400

            uploaded_file = (await request.files).get("photo")
            if uploaded_file:
                file_upload = FileUpload(
                    uploaded_file.filename,
                    uploaded_file.content_type,
                    uploaded_file.content_length,
                    uploaded_file.stream,
                )
        else:
            return jsonify(
                {
                    "code": "INVALID_REQUEST",
                    "message": "Content type must be multipart/form-data",
                }
            ), 400

        real_estate = map_real_estate(body)

        create_request = CreateRealEstateRequest(
            real_estate=real_estate, photo=file_upload
        )

        await create_real_estate_uc.execute(create_request)

    except (KeyError, ValueError, TypeError, FlowNotFound) as e:
        return jsonify({"code": "INVALID_REQUEST", "message": str(e)}), 400

    return "", 201
