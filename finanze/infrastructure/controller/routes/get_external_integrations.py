from domain.use_cases.get_external_integrations import GetExternalIntegrations
from quart import jsonify


async def get_external_integrations(
    get_external_integrations_uc: GetExternalIntegrations,
):
    integrations = await get_external_integrations_uc.execute()
    return jsonify(integrations), 200
