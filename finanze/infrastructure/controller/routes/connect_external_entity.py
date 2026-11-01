from uuid import UUID

from domain.exception.exceptions import (
    ProviderInstitutionNotFound,
    ProviderPsuTypeNotSupported,
)
from domain.external_entity import ConnectExternalEntityRequest, PsuType
from domain.external_integration import ExternalIntegrationId
from domain.use_cases.connect_external_entity import ConnectExternalEntity
from quart import jsonify, request


async def connect_external_entity(connect_external_entity_uc: ConnectExternalEntity):
    body = await request.get_json()
    redirect_host = request.headers.get("Host")
    accept_language = request.headers.get("Accept-Language") or None
    institution_id = body.get("institution_id")
    external_entity_id = body.get("external_entity_id")
    if external_entity_id:
        try:
            external_entity_id = UUID(external_entity_id)
        except ValueError:
            return jsonify({"message": "Error: invalid external_entity_id"}), 400

    if not institution_id and not external_entity_id:
        return jsonify(
            {"message": "Error: missing institution_id or external_entity_id"}
        ), 400

    provider = None
    raw_provider = body.get("provider")
    if raw_provider:
        try:
            provider = ExternalIntegrationId(raw_provider)
        except ValueError:
            return jsonify({"message": "Error: invalid provider"}), 400

    psu_type = None
    raw_psu_type = body.get("psu_type")
    if raw_psu_type:
        try:
            psu_type = PsuType(raw_psu_type)
        except ValueError:
            return jsonify({"message": "Error: invalid psu_type"}), 400

    connect_request = ConnectExternalEntityRequest(
        institution_id=institution_id,
        external_entity_id=external_entity_id,
        relink=body.get("relink", False),
        provider=provider,
        redirect_host=redirect_host,
        user_language=accept_language,
        completion_url=body.get("completion_url"),
        psu_type=psu_type,
    )
    try:
        result = await connect_external_entity_uc.execute(connect_request)
    except ProviderInstitutionNotFound:
        return jsonify({"message": "Error: institution not found"}), 404
    except ProviderPsuTypeNotSupported:
        return jsonify({"message": "Error: psu type not supported by institution"}), 400
    except ValueError as e:
        return jsonify({"message": f"{e}"}), 400

    return jsonify(result), 200
