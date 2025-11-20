from uuid import UUID
from flask import jsonify
from domain.use_cases.delete_template import DeleteTemplate


def delete_template(delete_template_uc: DeleteTemplate, template_id: str):
    try:
        template_uuid = UUID(template_id)
    except ValueError:
        return jsonify(
            {"code": "INVALID_REQUEST", "message": "Invalid UUID format"}
        ), 400

    delete_template_uc.execute(template_uuid)
    return "", 204
