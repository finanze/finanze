from uuid import UUID

from domain.exception.exceptions import ProviderInstitutionNotFound
from domain.external_entity import ConnectExternalEntityRequest
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

    connect_request = ConnectExternalEntityRequest(
        institution_id=institution_id,
        external_entity_id=external_entity_id,
        relink=body.get("relink", False),
        provider=None,
        redirect_host=redirect_host,
        user_language=accept_language,
    )
    try:
        result = await connect_external_entity_uc.execute(connect_request)
    except ProviderInstitutionNotFound:
        return jsonify({"message": "Error: institution not found"}), 404
    except ValueError as e:
        return jsonify({"message": f"{e}"}), 400

    return jsonify(result), 200
