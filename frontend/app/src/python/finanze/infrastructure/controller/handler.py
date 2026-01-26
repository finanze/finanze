from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

import urllib.parse

from infrastructure.controller.request_wrapper import RequestWrapper
from quart import Response, set_request

from domain.exception.exceptions import (
    EntityNotFound,
    TransactionNotFound,
    InvalidProvidedCredentials,
    InvalidUserCredentials,
    UnauthorizedToken,
    NoUserLogged,
    PermissionDenied,
    InvalidTemplateDefaultValue,
    InvalidToken,
    ExecutionConflict,
    BackupConflict,
    ExternalIntegrationRequired,
    IntegrationNotFound,
    IntegrationSetupError,
    IntegrationSetupErrorCode,
    TemplateNotFound,
    TooManyRequests,
    AddressNotFound,
)
from domain.data_init import DataEncryptedError
from domain.dezimal import Dezimal


def _to_jsonable(value):
    if value is None:
        return None

    if is_dataclass(value):
        return _to_jsonable(asdict(value))

    if isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, Dezimal):
        return float(value)

    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, UUID):
        return str(value)

    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            dt = dt.astimezone()
        return dt.isoformat()

    if isinstance(value, date):
        return value.isoformat()

    if isinstance(value, Enum):
        return _to_jsonable(value.value)

    if isinstance(value, dict):
        return {k: _to_jsonable(v) for k, v in value.items()}

    if isinstance(value, (list, tuple)):
        return [_to_jsonable(v) for v in value]

    return value


async def handle_request(router, method, path, body, headers):
    parsed = urllib.parse.urlparse(path)
    clean_path = parsed.path
    query_params = urllib.parse.parse_qs(parsed.query)

    req = RequestWrapper(method, clean_path, body, headers, query_params)

    handler, path_params = router.match(method, clean_path)

    if not handler:
        return {"status": 404, "data": {"code": "NOT_FOUND", "message": "Not Found"}}

    try:
        set_request(req)
        req.view_args = path_params
        res = await handler(req)

        status = 200
        headers = {}
        data = res

        if isinstance(res, tuple):
            if len(res) == 2:
                data, status = res
            elif len(res) >= 3:
                data, status, headers = res[0], res[1], res[2]
        elif isinstance(res, Response):
            data = res.data
            status = res.status_code
            headers = dict(res.headers)
            if res.mimetype:
                headers.setdefault("Content-Type", res.mimetype)

        if isinstance(data, Response):
            headers = dict(data.headers)
            if data.mimetype:
                headers.setdefault("Content-Type", data.mimetype)
            status = data.status_code
            data = data.data

        if is_dataclass(data):
            data = asdict(data)

        data = _to_jsonable(data)

        if data is None or data == "":  # 204
            return {"status": status or 204, "data": None, "headers": headers}

        if "Content-Type" not in headers and not isinstance(data, (bytes, bytearray)):
            headers["Content-Type"] = "application/json"

        return {"status": status, "data": data, "headers": headers}

    except Exception as e:
        status = 500
        original = getattr(e, "original_exception", e)
        data = {"code": "UNEXPECTED_ERROR", "message": str(original)}

        if isinstance(e, EntityNotFound):
            status = 404
            data = {"code": "ENTITY_NOT_FOUND", "message": str(e)}
        elif isinstance(e, TransactionNotFound):
            status = 404
            data = {"code": "TX_NOT_FOUND", "message": str(e)}
        elif isinstance(e, InvalidUserCredentials):
            status = 401
            data = {"code": "INVALID_CREDENTIALS", "message": str(e)}
        elif isinstance(e, InvalidProvidedCredentials):
            status = 400
            data = {"code": "INVALID_CREDENTIALS", "message": str(e)}
        elif isinstance(e, (DataEncryptedError, NoUserLogged)):
            status = 401
            data = {"code": "NOT_LOGGED"}
        elif isinstance(e, UnauthorizedToken):
            status = 401
            data = {
                "code": "UNAUTHORIZED_TOKEN",
                "message": "Token is invalid or expired",
            }
        elif isinstance(e, IntegrationNotFound):
            status = 404
            data = {"code": "INTEGRATION_NOT_FOUND", "message": str(e)}
        elif isinstance(e, IntegrationSetupError):
            status = (
                401 if e.code == IntegrationSetupErrorCode.INVALID_CREDENTIALS else 500
            )
            data = {}
        elif isinstance(e, ExternalIntegrationRequired):
            status = 409
            data = {
                "code": "REQUIRED_INTEGRATION",
                "details": {"required": e.required_integrations},
            }
        elif isinstance(e, TemplateNotFound):
            status = 404
            data = {"code": "TEMPLATE_NOT_FOUND", "message": "Template not found"}
        elif isinstance(e, InvalidTemplateDefaultValue):
            status = 400
            data = {"code": "INVALID_TEMPLATE_DEFAULT_VALUE", "message": str(e)}
        elif isinstance(e, InvalidToken):
            status = 400
            data = {"code": "INVALID_TOKEN", "message": str(e)}
        elif isinstance(e, ValueError):
            status = 400
            data = {"code": "INVALID_VALUE", "message": str(e)}
        elif isinstance(e, ExecutionConflict):
            status = 409
            data = {"code": "ALREADY_EXECUTING"}
        elif isinstance(e, TooManyRequests):
            status = 429
            data = {"code": "TOO_MANY_REQUESTS"}
        elif isinstance(e, AddressNotFound):
            status = 404
            data = {"code": "ADDRESS_NOT_FOUND", "message": str(e)}
        elif isinstance(e, BackupConflict):
            status = 409
            data = {"code": "BACKUP_CONFLICT", "message": str(e)}
        elif isinstance(e, PermissionDenied):
            status = 403
            data = {"code": "PERMISSION_DENIED", "message": str(e)}

        router.logger.exception(f"Error handling {method} {path}")
        return {
            "status": status,
            "data": _to_jsonable(data),
            "headers": {"Content-Type": "application/json"},
        }
