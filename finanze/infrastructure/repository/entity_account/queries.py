from enum import Enum


class EntityAccountQueries(str, Enum):
    INSERT = """
        INSERT INTO entity_accounts (id, name, entity_id, created_at)
        VALUES (?, ?, ?, ?)
    """

    GET_BY_ENTITY_ID = """
        SELECT id, name, entity_id, created_at, deleted_at
        FROM entity_accounts
        WHERE entity_id = ? AND deleted_at IS NULL
    """

    GET_BY_ID = """
        SELECT id, name, entity_id, created_at, deleted_at
        FROM entity_accounts
        WHERE id = ? AND deleted_at IS NULL
    """

    SOFT_DELETE = "UPDATE entity_accounts SET deleted_at = ? WHERE id = ?"

    SOFT_DELETE_BY_ENTITY_ID = "UPDATE entity_accounts SET deleted_at = ? WHERE entity_id = ? AND deleted_at IS NULL"
