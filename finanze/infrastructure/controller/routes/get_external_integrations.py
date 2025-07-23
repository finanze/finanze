from domain.use_cases.get_external_integrations import GetExternalIntegrations
from flask import jsonify


def get_external_integrations(get_external_integrations_uc: GetExternalIntegrations):
    integrations = get_external_integrations_uc.execute()
    return jsonify(integrations), 200
