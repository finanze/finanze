from domain.ai import AITask, ValidateAIModelRequest
from domain.external_integration import ExternalIntegrationId
from domain.use_cases.validate_ai_model import ValidateAIModel
from quart import jsonify, request


async def validate_ai_model(validate_ai_model_uc: ValidateAIModel):
    body = await request.get_json()
    try:
        upstream_provider = body.get("upstream_provider")
        validate_request = ValidateAIModelRequest(
            provider=ExternalIntegrationId(body["provider"]),
            model=str(body["model"]),
            task=AITask(body["task"]),
            upstream_provider=str(upstream_provider) if upstream_provider else None,
        )
    except (KeyError, ValueError, TypeError, AttributeError) as e:
        return jsonify({"code": "INVALID_REQUEST", "message": str(e)}), 400

    result = await validate_ai_model_uc.execute(validate_request)
    return jsonify(result), 200
