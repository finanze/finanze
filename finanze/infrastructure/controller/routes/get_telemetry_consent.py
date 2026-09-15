from domain.use_cases.get_telemetry_consent import GetTelemetryConsent
from quart import jsonify


async def get_telemetry_consent(get_telemetry_consent_uc: GetTelemetryConsent):
    consent = await get_telemetry_consent_uc.execute()
    return jsonify(
        {
            "errorReporting": consent.error_reporting,
            "installId": str(consent.install_id) if consent.install_id else None,
        }
    ), 200
