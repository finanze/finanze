from datetime import datetime
from uuid import uuid4

from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

DDL = """
      ALTER TABLE account_transactions ADD COLUMN counterparty TEXT;
      ALTER TABLE account_transactions ADD COLUMN iban TEXT;
      ALTER TABLE account_transactions ADD COLUMN linked_tx TEXT;
      ALTER TABLE account_transactions ADD COLUMN labels_locked BOOLEAN NOT NULL DEFAULT FALSE;
      ALTER TABLE account_transactions ADD COLUMN external_unmatched_at DATETIME;

      CREATE INDEX idx_account_entity_ref ON account_transactions (entity_id, ref);

      CREATE TABLE labels
      (
          id          CHAR(36)    NOT NULL PRIMARY KEY,
          key         VARCHAR(64) UNIQUE,
          name        TEXT,
          description TEXT,
          color       VARCHAR(16),
          icon        VARCHAR(64),
          category    VARCHAR(16) NOT NULL DEFAULT 'EXPENSE',
          created_at  DATETIME    NOT NULL,
          CHECK (key IS NOT NULL OR name IS NOT NULL)
      );

      CREATE TABLE labeling_rules
      (
          id         CHAR(36)    NOT NULL PRIMARY KEY,
          name       TEXT,
          enabled    BOOLEAN     NOT NULL DEFAULT TRUE,
          kind       VARCHAR(16) NOT NULL DEFAULT 'MATCH',
          conditions TEXT        NOT NULL,
          created_at DATETIME    NOT NULL,
          updated_at DATETIME    NOT NULL
      );

      CREATE TABLE labeling_rule_labels
      (
          rule_id  CHAR(36) NOT NULL REFERENCES labeling_rules (id) ON DELETE CASCADE,
          label_id CHAR(36) NOT NULL REFERENCES labels (id) ON DELETE CASCADE,
          PRIMARY KEY (rule_id, label_id)
      );

      CREATE INDEX idx_labeling_rule_labels_label_id ON labeling_rule_labels (label_id);

      CREATE TABLE account_transaction_labels
      (
          tx_id      CHAR(36)    NOT NULL REFERENCES account_transactions (id) ON DELETE CASCADE,
          label_id   CHAR(36)    NOT NULL REFERENCES labels (id) ON DELETE CASCADE,
          origin     VARCHAR(16) NOT NULL,
          rule_id    CHAR(36) REFERENCES labeling_rules (id) ON DELETE SET NULL,
          provider   TEXT,
          confidence TEXT,
          created_at DATETIME    NOT NULL,
          PRIMARY KEY (tx_id, label_id)
      );

      CREATE INDEX idx_atl_label_id ON account_transaction_labels (label_id);
      CREATE INDEX idx_atl_rule_id ON account_transaction_labels (rule_id);

      CREATE TABLE account_transfer_pairs
      (
          tx_id        CHAR(36) NOT NULL PRIMARY KEY REFERENCES account_transactions (id) ON DELETE CASCADE,
          paired_tx_id CHAR(36) NOT NULL REFERENCES account_transactions (id) ON DELETE CASCADE,
          rule_id      CHAR(36) REFERENCES labeling_rules (id) ON DELETE CASCADE,
          created_at   DATETIME NOT NULL
      );

      CREATE INDEX idx_atp_paired_tx_id ON account_transfer_pairs (paired_tx_id);
      CREATE INDEX idx_atp_rule_id ON account_transfer_pairs (rule_id);

      INSERT INTO external_integrations (id, name, type, status)
      VALUES ('OPENROUTER', 'OpenRouter', 'AI_PROVIDER', 'OFF');
      """

INCOME = "INCOME"
EXPENSE = "EXPENSE"
EXCLUDED = "EXCLUDED"

BASE_LABELS = [
    ("salary", "#16a34a", "briefcase", INCOME),
    ("business_income", "#15803d", "store", INCOME),
    ("rental_income", "#0d9488", "key-round", INCOME),
    ("refunds", "#0891b2", "rotate-ccw", INCOME),
    ("gifts_received", "#db2777", "gift", INCOME),
    ("interest", "#65a30d", "percent", INCOME),
    ("other_income", "#4ade80", "circle-plus", INCOME),
    ("housing", "#9333ea", "house", EXPENSE),
    ("utilities", "#eab308", "zap", EXPENSE),
    ("groceries", "#f97316", "shopping-cart", EXPENSE),
    ("restaurants", "#ef4444", "utensils", EXPENSE),
    ("transport", "#3b82f6", "car", EXPENSE),
    ("shopping", "#ec4899", "shopping-bag", EXPENSE),
    ("subscriptions", "#8b5cf6", "repeat", EXPENSE),
    ("health", "#f43f5e", "heart-pulse", EXPENSE),
    ("insurance", "#64748b", "shield", EXPENSE),
    ("education", "#0ea5e9", "graduation-cap", EXPENSE),
    ("leisure", "#a855f7", "ticket", EXPENSE),
    ("travel", "#06b6d4", "plane", EXPENSE),
    ("personal_care", "#f472b6", "sparkles", EXPENSE),
    ("pets", "#a16207", "paw-print", EXPENSE),
    ("family", "#fb923c", "baby", EXPENSE),
    ("gifts_donations", "#be185d", "hand-heart", EXPENSE),
    ("taxes", "#78716c", "landmark", EXPENSE),
    ("bank_fees", "#dc2626", "receipt", EXPENSE),
    ("cash_withdrawal", "#84cc16", "banknote", EXPENSE),
    ("debt_payments", "#b91c1c", "credit-card", EXPENSE),
    ("other_expense", "#9ca3af", "circle-minus", EXPENSE),
    ("internal_transfer", "#6b7280", "arrow-left-right", EXCLUDED),
    ("savings_investment", "#2563eb", "piggy-bank", EXCLUDED),
]

DEFAULT_RULES = [
    ("INTEREST", "interest"),
    ("FEE", "bank_fees"),
]

DEFAULT_TRANSFER_RULE = ('{"max_days": 3}', "internal_transfer")


class V01100AccountTxLabeling(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.11.0:0_account_tx_labeling"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        for statement in self.parse_block(DDL):
            await cursor.execute(statement)

        now = datetime.now().astimezone().isoformat()
        label_ids = {}
        for key, color, icon, category in BASE_LABELS:
            label_id = str(uuid4())
            label_ids[key] = label_id
            await cursor.execute(
                """
                INSERT INTO labels (id, key, name, description, color, icon, category, created_at)
                VALUES (?, ?, NULL, NULL, ?, ?, ?, ?)
                """,
                (label_id, key, color, icon, category, now),
            )

        for tx_type, label_key in DEFAULT_RULES:
            rule_id = await self._insert_rule(
                cursor,
                "MATCH",
                f'{{"types": ["{tx_type}"]}}',
                label_ids[label_key],
                now,
            )
            await cursor.execute(
                """
                INSERT INTO account_transaction_labels (tx_id, label_id, origin, rule_id, provider, confidence, created_at)
                SELECT id, ?, 'RULE', ?, NULL, NULL, ?
                FROM account_transactions
                WHERE type = ?
                """,
                (label_ids[label_key], rule_id, now, tx_type),
            )

        conditions, label_key = DEFAULT_TRANSFER_RULE
        await self._insert_rule(
            cursor, "TRANSFER", conditions, label_ids[label_key], now
        )

    @staticmethod
    async def _insert_rule(
        cursor: DBCursor, kind: str, conditions: str, label_id: str, now: str
    ) -> str:
        rule_id = str(uuid4())
        await cursor.execute(
            """
            INSERT INTO labeling_rules (id, name, enabled, kind, conditions, created_at, updated_at)
            VALUES (?, NULL, TRUE, ?, ?, ?, ?)
            """,
            (rule_id, kind, conditions, now, now),
        )
        await cursor.execute(
            "INSERT INTO labeling_rule_labels (rule_id, label_id) VALUES (?, ?)",
            (rule_id, label_id),
        )
        return rule_id
