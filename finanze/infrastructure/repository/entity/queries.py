from enum import Enum


class EntityQueries(str, Enum):
    INSERT = """
        INSERT INTO entities (id, name, natural_id, type, origin, icon_url)
        VALUES (?, ?, ?, ?, ?, ?)
    """

    UPDATE = """
        UPDATE entities
        SET name       = ?,
            natural_id = ?,
            type       = ?,
            origin     = ?,
            icon_url   = ?
        WHERE id = ?
    """

    GET_BY_ID = "SELECT * FROM entities WHERE id = ?"
    GET_ALL = "SELECT * FROM entities"
    GET_BY_NATURAL_ID = "SELECT * FROM entities WHERE natural_id = ?"
    GET_BY_NAME = "SELECT * FROM entities WHERE name = ?"
    DELETE_BY_ID = "DELETE FROM entities WHERE id = ?"

    GET_DISABLED_ENTITIES = """
        WITH latest_manual AS (
            SELECT DISTINCT entity_id
            FROM virtual_data_imports
            WHERE import_id = (
                SELECT import_id
                FROM virtual_data_imports
                ORDER BY date DESC
                LIMIT 1
            )
            AND entity_id IS NOT NULL
        )
        SELECT e.*
        FROM entities e
            LEFT JOIN entity_credentials c ON e.id = c.entity_id
            LEFT JOIN external_entities ee ON e.id = ee.entity_id
            LEFT JOIN latest_manual lm ON e.id = lm.entity_id
        WHERE (
            e.origin = 'EXTERNALLY_PROVIDED' AND ee.entity_id IS NULL
        )
        OR (
            e.origin = 'NATIVE' AND e.type = 'FINANCIAL_INSTITUTION' AND c.entity_id IS NULL
        )
        OR (
            e.origin = 'MANUAL' AND e.type = 'FINANCIAL_INSTITUTION' AND lm.entity_id IS NULL
        )
    """


class ExternalEntityQueries(str, Enum):
    UPSERT = """
        INSERT INTO external_entities
            (id, entity_id, status, provider, date, provider_instance_id, payload)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT
            (id)
        DO UPDATE SET
            status = excluded.status,
            provider_instance_id = excluded.provider_instance_id,
            date = excluded.date,
            payload = excluded.payload
    """

    UPDATE_STATUS = """
        UPDATE external_entities
        SET status = ?
        WHERE id = ?
    """

    GET_BY_ID = "SELECT * FROM external_entities WHERE id = ?"
    GET_BY_ENTITY_ID = "SELECT * FROM external_entities WHERE entity_id = ?"
    DELETE_BY_ID = "DELETE FROM external_entities WHERE id = ?"
    GET_ALL = "SELECT * FROM external_entities"
