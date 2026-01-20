import logging
import traceback

from domain.exception.exceptions import ExternalEntityLinkError, ExternalEntityNotFound
from domain.external_entity import CompleteExternalEntityLinkRequest
from domain.use_cases.complete_external_entity_connection import (
    CompleteExternalEntityConnection,
)
from quart import request

logger = logging.getLogger(__name__)


async def complete_external_entity_connection(
    complete_external_entity_connection_uc: CompleteExternalEntityConnection,
):
    args = request.args
    external_entity_id = args.get("external_entity_id")

    completion_request = CompleteExternalEntityLinkRequest(
        payload=args, external_entity_id=external_entity_id
    )
    try:
        await complete_external_entity_connection_uc.execute(completion_request)
    except ExternalEntityNotFound:
        return error_connecting_external_entity(404)
    except ExternalEntityLinkError as e:
        return error_connecting_external_entity(500, e.details)
    except ValueError:
        return error_connecting_external_entity(400)
    except Exception:
        logger.error(traceback.format_exc())
        return error_connecting_external_entity(500)

    return successfully_connected_external_entity()


async def successfully_connected_external_entity():
    html = """
    <html>
        <head>
            <title>OK</title>
        </head>
        <body>
            <h1>✅</h1>
        </body>
    """
    return html, 200


async def error_connecting_external_entity(http_status, details=None):
    error_detail = f"<p>{details}</p>" if details else ""
    html = f"""
    <html>
        <head>
            <title>Error {http_status}</title>
        </head>
        <body>
            <h1>❌</h1>
            {error_detail}
        </body>
    """
    return html, http_status
