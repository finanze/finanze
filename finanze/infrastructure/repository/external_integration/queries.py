from enum import Enum


class ExternalIntegrationQueries(str, Enum):
    DEACTIVATE = """
        UPDATE external_integrations
        SET status  = ?,
            payload = NULL
        WHERE id = ?
    """

    ACTIVATE = """
        UPDATE external_integrations
        SET status  = ?,
            payload = ?
        WHERE id = ?
    """

    UPDATE_PAYLOAD = """
        UPDATE external_integrations
        SET payload = ?
        WHERE id = ?
          AND status = ?
    """

    GET_PAYLOAD = "SELECT payload FROM external_integrations WHERE id = ? AND status = ? AND payload IS NOT NULL"

    GET_PAYLOADS_BY_TYPE = """
        SELECT id, payload
        FROM external_integrations
        WHERE type = ?
          AND status = ?
          AND payload IS NOT NULL
    """

    GET_ALL = """
        SELECT id, name, type, status
        FROM external_integrations
    """
