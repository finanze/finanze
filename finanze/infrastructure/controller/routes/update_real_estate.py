import json
from uuid import UUID

from domain.exception.exceptions import FlowNotFound, RealEstateNotFound
from domain.file_upload import FileUpload
from domain.real_estate import UpdateRealEstateRequest
from domain.use_cases.update_real_estate import UpdateRealEstate
from quart import jsonify, request
from infrastructure.controller.mappers.real_estate_mapper import map_real_estate


async def update_real_estate(update_real_estate_uc: UpdateRealEstate):
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
            # Handle regular JSON request for backward compatibility
            body = await request.get_json()

        if not body.get("id"):
            return jsonify(
                {"code": "INVALID_REQUEST", "message": "ID is required for update"}
            ), 400

        real_estate_id = UUID(body["id"])
        real_estate = map_real_estate(body, real_estate_id=real_estate_id)
        remove_unassigned_flows = body.get("remove_unassigned_flows", False)

        update_request = UpdateRealEstateRequest(
            real_estate=real_estate,
            remove_unassigned_flows=remove_unassigned_flows,
            photo=file_upload,
        )

    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"code": "INVALID_REQUEST", "message": str(e)}), 400

    try:
        await update_real_estate_uc.execute(update_request)
    except FlowNotFound as e:
        return jsonify({"code": "INVALID_REQUEST", "message": str(e)}), 400
    except RealEstateNotFound as e:
        return jsonify({"code": "NOT_FOUND", "message": str(e)}), 404

    return "", 204
