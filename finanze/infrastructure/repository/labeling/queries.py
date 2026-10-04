from enum import Enum


class LabelQueries(str, Enum):
    GET_ALL = """
        SELECT id, key, name, description, color, icon, category
        FROM labels
        ORDER BY key IS NULL, created_at, name
    """

    GET_BY_ID = """
        SELECT id, key, name, description, color, icon, category
        FROM labels
        WHERE id = ?
    """

    GET_USAGE = """
        SELECT label_id, COUNT(*) AS usage
        FROM account_transaction_labels
        GROUP BY label_id
    """

    INSERT = """
        INSERT INTO labels (id, key, name, description, color, icon, category, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """

    UPDATE = """
        UPDATE labels
        SET name = ?, description = ?, color = ?, icon = ?, category = ?
        WHERE id = ?
    """

    DELETE = "DELETE FROM labels WHERE id = ?"


class LabelingRuleQueries(str, Enum):
    GET_ALL = """
        SELECT r.id, r.name, r.enabled, r.kind, r.conditions, rl.label_id
        FROM labeling_rules r
            LEFT JOIN labeling_rule_labels rl ON rl.rule_id = r.id
        ORDER BY r.created_at, r.id
    """

    GET_ENABLED = """
        SELECT r.id, r.name, r.enabled, r.kind, r.conditions, rl.label_id
        FROM labeling_rules r
            LEFT JOIN labeling_rule_labels rl ON rl.rule_id = r.id
        WHERE r.enabled = TRUE
        ORDER BY r.created_at, r.id
    """

    GET_BY_ID = """
        SELECT r.id, r.name, r.enabled, r.kind, r.conditions, rl.label_id
        FROM labeling_rules r
            LEFT JOIN labeling_rule_labels rl ON rl.rule_id = r.id
        WHERE r.id = ?
    """

    INSERT = """
        INSERT INTO labeling_rules (id, name, enabled, kind, conditions, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """

    UPDATE = """
        UPDATE labeling_rules
        SET name = ?, enabled = ?, conditions = ?, updated_at = ?
        WHERE id = ?
    """

    INSERT_LABEL = "INSERT INTO labeling_rule_labels (rule_id, label_id) VALUES (?, ?)"
    DELETE_LABELS = "DELETE FROM labeling_rule_labels WHERE rule_id = ?"
    DELETE = "DELETE FROM labeling_rules WHERE id = ?"


class TransactionLabelQueries(str, Enum):
    INSERT = """
        INSERT OR IGNORE INTO account_transaction_labels
            (tx_id, label_id, origin, rule_id, provider, confidence, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """

    DELETE_BY_RULE = """
        DELETE FROM account_transaction_labels
        WHERE rule_id = ?
          AND origin = 'RULE'
          AND tx_id IN (SELECT id FROM account_transactions WHERE labels_locked = FALSE)
    """

    SET_LINKED_TX = "UPDATE account_transactions SET linked_tx = ? WHERE id = ?"

    GET_TRANSFER_PAIR = """
        SELECT tx_id, paired_tx_id, rule_id FROM account_transfer_pairs WHERE tx_id = ?
    """

    INSERT_TRANSFER_PAIR = """
        INSERT INTO account_transfer_pairs (tx_id, paired_tx_id, rule_id, created_at)
        VALUES (?, ?, ?, ?)
    """

    DELETE_TRANSFER_PAIR = """
        DELETE FROM account_transfer_pairs WHERE tx_id = ? OR paired_tx_id = ?
    """

    DELETE_TRANSFER_PAIRS_BY_RULE = """
        DELETE FROM account_transfer_pairs
        WHERE rule_id = ?
          AND tx_id IN (SELECT id FROM account_transactions WHERE labels_locked = FALSE)
          AND paired_tx_id IN (SELECT id FROM account_transactions WHERE labels_locked = FALSE)
    """

    TX_EXISTS = "SELECT 1 FROM account_transactions WHERE id = ?"

    CLASSIFICATION_BASE = """
        SELECT at.id, at.entity_id, at.ref, at.labels_locked, at.linked_tx, at.external_unmatched_at
        FROM account_transactions at
    """

    CLASSIFICATION_FILTER = """
        (at.labels_locked = TRUE
            OR at.linked_tx IS NOT NULL
            OR at.external_unmatched_at IS NOT NULL
            OR EXISTS (SELECT 1 FROM account_transaction_labels l WHERE l.tx_id = at.id)
            OR EXISTS (SELECT 1 FROM account_transfer_pairs p WHERE p.tx_id = at.id))
    """
