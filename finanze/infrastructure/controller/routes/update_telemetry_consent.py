from domain.telemetry import TelemetryConsent
from domain.use_cases.update_telemetry_consent import UpdateTelemetryConsent
from quart import jsonify, request


async def update_telemetry_consent(update_telemetry_consent_uc: UpdateTelemetryConsent):
    body = await request.get_json()

    if not isinstance(body, dict):
        return jsonify({"code": "INVALID_CONSENT", "message": "Invalid body"}), 400

    consent = TelemetryConsent(
        error_reporting=body.get("errorReporting") is True,
        session_replay=body.get("sessionReplay") is True,
    )

    saved = await update_telemetry_consent_uc.execute(consent)

    return jsonify(
        {
            "errorReporting": saved.error_reporting,
            "sessionReplay": saved.session_replay,
            "installId": str(saved.install_id) if saved.install_id else None,
        }
    ), 200
