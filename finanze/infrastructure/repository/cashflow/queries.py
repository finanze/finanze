from enum import Enum


class IgnoredRecurringMovementQueries(str, Enum):
    GET_ALL = """
        SELECT id, key, type, currency, amount
        FROM ignored_recurring_movements
        ORDER BY created_at
    """

    INSERT = """
        INSERT INTO ignored_recurring_movements (id, key, type, currency, amount, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """

    DELETE = "DELETE FROM ignored_recurring_movements WHERE id = ?"
