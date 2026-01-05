from enum import Enum


class SessionsQueries(str, Enum):
    GET = "SELECT created_at, expiration, payload FROM entity_sessions WHERE entity_id = ?"

    INSERT = """
        INSERT INTO entity_sessions (entity_id, created_at, expiration, payload)
        VALUES (?, ?, ?, ?)
    """

    DELETE = "DELETE FROM entity_sessions WHERE entity_id = ?"
