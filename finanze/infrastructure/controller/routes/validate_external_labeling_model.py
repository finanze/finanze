from domain.external_integration import ExternalIntegrationId
from domain.external_labeling import ValidateExternalLabelingModelRequest
from domain.use_cases.validate_external_labeling_model import (
    ValidateExternalLabelingModel,
)
from quart import jsonify, request


async def validate_external_labeling_model(
    validate_external_labeling_model_uc: ValidateExternalLabelingModel,
):
    body = await request.get_json()
    try:
        upstream_provider = body.get("upstream_provider")
        validate_request = ValidateExternalLabelingModelRequest(
            provider=ExternalIntegrationId(body["provider"]),
            model=str(body["model"]),
            upstream_provider=str(upstream_provider) if upstream_provider else None,
        )
    except (KeyError, ValueError, TypeError, AttributeError) as e:
        return jsonify({"code": "INVALID_REQUEST", "message": str(e)}), 400

    result = await validate_external_labeling_model_uc.execute(validate_request)
    return jsonify(result), 200
