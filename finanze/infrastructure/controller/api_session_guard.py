from quart import Quart, jsonify, request

from domain.use_cases.authorize_api_access import AuthorizeApiAccess

PUBLIC_PATHS = frozenset(
    {
        "/api/v1/status",
        "/api/v1/login",
        "/oauth/callback",
        "/auth/callback",
        "/api/v1/entities/external/complete",
    }
)


def register_api_session_guard(app: Quart, authorize_api_access: AuthorizeApiAccess):
    @app.before_request
    async def require_api_session():
        if request.method == "OPTIONS" or request.endpoint == "static":
            return None
        if request.path.rstrip("/") in PUBLIC_PATHS:
            return None

        scheme, _, token = (request.headers.get("Authorization") or "").partition(" ")
        session_token = token.strip() if scheme.lower() == "bearer" else None

        if await authorize_api_access.execute(session_token or None):
            return None

        return jsonify({"code": "NOT_LOGGED", "message": "Session required"}), 401
