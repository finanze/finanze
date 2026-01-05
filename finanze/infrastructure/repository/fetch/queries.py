from enum import Enum


class LastFetchesQueries(str, Enum):
    GET_BY_ENTITY_ID = (
        "SELECT entity_id, feature, date FROM last_fetches WHERE entity_id = ?"
    )

    GET_GROUPED_BY_ENTITY = """
        SELECT lf.entity_id,
               e.name       as entity_name,
               e.natural_id as entity_natural_id,
               e.type       as entity_type,
               e.origin     as entity_origin,
               e.icon_url   AS icon_url,
               lf.feature,
               lf.date
        FROM last_fetches lf
            JOIN entities e ON lf.entity_id = e.id
        WHERE feature = ?
    """

    UPSERT = """
        INSERT OR REPLACE INTO last_fetches (entity_id, feature, date)
        VALUES (?, ?, ?)
    """
