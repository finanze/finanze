from enum import Enum


class HistoricQueries(str, Enum):
    INSERT_HISTORIC_ENTRY = """
        INSERT INTO investment_historic (id, name, invested, repaid, returned, currency,
                                         last_invest_date,
                                         last_tx_date, effective_maturity, net_return, fees,
                                         retentions, interests, state, entity_id, product_type,
                                         interest_rate, gross_interest_rate, maturity,
                                         extended_maturity, type, business_type, created_at)
        VALUES (:id, :name, :invested, :repaid, :returned, :currency, :last_invest_date,
                :last_tx_date, :effective_maturity, :net_return, :fees,
                :retentions, :interests, :state, :entity_id, :product_type,
                :interest_rate, :gross_interest_rate, :maturity,
                :extended_maturity, :type, :business_type, :created_at)
    """

    INSERT_HISTORIC_TX = """
        INSERT INTO investment_historic_txs
            (tx_id, historic_entry_id)
        VALUES (?, ?)
    """

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

    DELETE_BY_ENTITY = "DELETE FROM investment_historic WHERE entity_id = ?"

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
    """
