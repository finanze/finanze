from uuid import UUID

from domain.exception.exceptions import ExternalEntityNotFound
from domain.external_entity import DeleteExternalEntityRequest
from domain.use_cases.delete_external_entity import DeleteExternalEntity


async def delete_external_entity(
    delete_external_entity_uc: DeleteExternalEntity, external_entity_id: str
):
    try:
        ee_id = UUID(external_entity_id)
    except ValueError:
        return {"message": "Invalid ID format"}, 400

    delete_request = DeleteExternalEntityRequest(ee_id)

    try:
        await delete_external_entity_uc.execute(delete_request)
    except ExternalEntityNotFound:
        return {"message": "External entity not found"}, 404

    return "", 204
