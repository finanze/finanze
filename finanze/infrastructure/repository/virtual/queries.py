from enum import Enum


class VirtualImportQueries(str, Enum):
    INSERT = """
        INSERT INTO virtual_data_imports (id, import_id, global_position_id, source, date, feature, entity_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """

    DELETE_BY_IMPORT_AND_FEATURE = """
        DELETE
        FROM virtual_data_imports
        WHERE import_id = ?
          AND feature = ?
    """

    DELETE_BY_IMPORT_FEATURE_AND_ENTITY = """
        DELETE FROM virtual_data_imports
        WHERE import_id = ? AND feature = ? AND entity_id = ?
    """

    GET_LAST_IMPORT_RECORDS_BASE = """
        WITH latest_import_details AS (
            SELECT import_id
            FROM virtual_data_imports
            {where}
            ORDER BY date DESC
            LIMIT 1
        )
        SELECT vdi.*
        FROM virtual_data_imports vdi
            JOIN latest_import_details lid ON vdi.import_id = lid.import_id
    """
