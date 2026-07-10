from enum import Enum


class TrackedUpdatesQueries(str, Enum):
    GET_BY_USE_CASE = (
        "SELECT last_executed_at FROM tracked_updates WHERE use_case_name = ?"
    )

    UPSERT = """
        INSERT OR REPLACE INTO tracked_updates (id, use_case_name, last_executed_at)
        VALUES (?, ?, ?)
    """
