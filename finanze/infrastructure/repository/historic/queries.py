from enum import Enum


class HistoricQueries(str, Enum):
    INSERT_HISTORIC_ENTRY = """
        INSERT INTO investment_historic (id, name, invested, repaid, returned, currency,
                                         last_invest_date,
                                         last_tx_date, effective_maturity, net_return, fees,
                                         retentions, interests, state, entity_id, product_type,
                                         interest_rate, gross_interest_rate, maturity,
                                         extended_maturity, type, business_type, created_at,
                                         entity_account_id, source, manual_key)
        VALUES (:id, :name, :invested, :repaid, :returned, :currency, :last_invest_date,
                :last_tx_date, :effective_maturity, :net_return, :fees,
                :retentions, :interests, :state, :entity_id, :product_type,
                :interest_rate, :gross_interest_rate, :maturity,
                :extended_maturity, :type, :business_type, :created_at,
                :entity_account_id, :source, :manual_key)
    """

    INSERT_HISTORIC_TX = """
        INSERT INTO investment_historic_txs
            (tx_id, historic_entry_id)
        VALUES (?, ?)
    """

    SELECT_ENTRY_BASE = """
        SELECT h.*,
               e.id         AS entity_id,
               e.name       AS entity_name,
               e.natural_id AS entity_natural_id,
               e.type       as entity_type,
               e.origin     as entity_origin,
               e.icon_url   AS icon_url
        FROM investment_historic h
            JOIN entities e ON h.entity_id = e.id
    """

    GET_BY_ID = SELECT_ENTRY_BASE + "\nWHERE h.id = ?"

    GET_BY_MANUAL_KEY = SELECT_ENTRY_BASE + "\nWHERE h.manual_key = ?"

    GET_MANUAL_BY_ENTITY = (
        SELECT_ENTRY_BASE + "\nWHERE h.source = 'MANUAL' AND h.entity_id = ?"
    )

    DELETE_BY_ID = "DELETE FROM investment_historic WHERE id = ?"

    DELETE_BY_MANUAL_KEY = "DELETE FROM investment_historic WHERE manual_key = ?"

    SELECT_RELATED_TXS_BASE = """
        SELECT t.*,
               e.id         AS entity_id,
               e.name       AS entity_name,
               e.natural_id AS entity_natural_id,
               e.type       as entity_type,
               e.origin     as entity_origin,
               e.icon_url   AS icon_url,
               h_txs.historic_entry_id
        FROM investment_historic_txs h_txs
            JOIN investment_transactions t ON h_txs.tx_id = t.id
            JOIN entities e ON t.entity_id = e.id
        WHERE h_txs.historic_entry_id IN ({placeholders})
    """

    DELETE_BY_ENTITY_ACCOUNT = (
        "DELETE FROM investment_historic WHERE entity_account_id = ?"
    )

    GET_BY_FILTERS_BASE = """
        SELECT h.*,
               e.id         AS entity_id,
               e.name       AS entity_name,
               e.natural_id AS entity_natural_id,
               e.type       as entity_type,
               e.origin     as entity_origin,
               e.icon_url   AS icon_url
        FROM investment_historic h
            JOIN entities e ON h.entity_id = e.id
            LEFT JOIN entity_accounts ea ON h.entity_account_id = ea.id
        WHERE (h.entity_account_id IS NULL OR ea.deleted_at IS NULL)
    """
