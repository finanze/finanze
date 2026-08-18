from enum import Enum


class GainsTimelineQueries(str, Enum):
    GET_REAL_SNAPSHOTS_BASE = """
        SELECT gp.id, gp.entity_id, COALESCE(gp.entity_account_id, '') AS ea_key,
               gp.source, gp.date, ea.deleted_at
        FROM global_positions gp
            LEFT JOIN entity_accounts ea ON gp.entity_account_id = ea.id
        WHERE gp.source = 'REAL'
    """

    GET_BATCHED_IMPORTS_BASE = """
        SELECT vdi.source AS source,
               vdi.import_id AS import_id,
               vdi.date AS import_date,
               vdi.global_position_id AS gp_id
        FROM virtual_data_imports vdi
        WHERE vdi.source IN ('MANUAL', 'SHEETS')
          AND (vdi.feature = 'POSITION' OR vdi.feature IS NULL)
    """

    GET_ASSET_VALUATIONS_BASE = """
        SELECT global_position_id,
               'STOCK_ETF' AS product_type,
               COALESCE(NULLIF(isin, ''), NULLIF(ticker, ''), name) AS asset_key,
               NULL AS portfolio_name,
               type AS equity_type,
               currency,
               market_value,
               shares AS quantity,
               NULL AS quantity_unit,
               NULL AS commodity_type,
               NULL AS weight,
               NULL AS weight_unit,
               initial_investment AS cost_basis,
               NULL AS interest_rate,
               NULL AS start_date,
               NULL AS maturity,
               NULL AS extended_maturity,
               NULL AS extended_interest_rate,
             NULL AS late_interest_rate,
             NULL AS wallet_id
        FROM stock_positions
        UNION ALL
         SELECT f.global_position_id,
               'FUND' AS product_type,
             COALESCE(NULLIF(f.isin, ''), f.name) AS asset_key,
             p.name AS portfolio_name,
             NULL AS equity_type,
             f.currency,
             f.market_value,
             f.shares AS quantity,
               NULL AS quantity_unit,
               NULL AS commodity_type,
               NULL AS weight,
               NULL AS weight_unit,
             f.initial_investment AS cost_basis,
               NULL AS interest_rate,
               NULL AS start_date,
               NULL AS maturity,
               NULL AS extended_maturity,
               NULL AS extended_interest_rate,
               NULL AS late_interest_rate,
               NULL AS wallet_id
         FROM fund_positions f
             LEFT JOIN fund_portfolios p ON p.id = f.portfolio_id
        UNION ALL
        SELECT p.global_position_id,
               'CRYPTO' AS product_type,
               COALESCE(NULLIF(p.contract_address, ''), NULLIF(p.symbol, ''), p.name) AS asset_key,
               NULL AS portfolio_name,
               NULL AS equity_type,
               p.currency,
               p.market_value,
               p.amount AS quantity,
               NULL AS quantity_unit,
               NULL AS commodity_type,
               NULL AS weight,
               NULL AS weight_unit,
               i.initial_investment AS cost_basis,
               NULL AS interest_rate,
               NULL AS start_date,
               NULL AS maturity,
               NULL AS extended_maturity,
               NULL AS extended_interest_rate,
             NULL AS late_interest_rate,
             p.wallet_id
        FROM crypto_currency_positions p
            LEFT JOIN crypto_currency_initial_investments i
                ON p.id = i.crypto_currency_position
        UNION ALL
        SELECT global_position_id,
               'COMMODITY' AS product_type,
                             type || ':' || COALESCE(NULLIF(name, ''), type) AS asset_key,
               NULL AS portfolio_name,
               NULL AS equity_type,
               currency,
               market_value,
               amount AS quantity,
                             unit AS quantity_unit,
                             type AS commodity_type,
                             amount AS weight,
                             unit AS weight_unit,
               initial_investment AS cost_basis,
               NULL AS interest_rate,
               NULL AS start_date,
               NULL AS maturity,
               NULL AS extended_maturity,
               NULL AS extended_interest_rate,
             NULL AS late_interest_rate,
             NULL AS wallet_id
        FROM commodity_positions
        UNION ALL
        SELECT global_position_id,
               'DEPOSIT' AS product_type,
                             'DEPOSIT:' || substr(creation, 1, 10) || ':' || maturity || ':' || amount || ':' || currency AS asset_key,
               NULL AS portfolio_name,
               NULL AS equity_type,
               currency,
               amount AS market_value,
               NULL AS quantity,
               NULL AS quantity_unit,
                             NULL AS commodity_type,
                             NULL AS weight,
                             NULL AS weight_unit,
               amount AS cost_basis,
               interest_rate,
               creation AS start_date,
               maturity,
               NULL AS extended_maturity,
               NULL AS extended_interest_rate,
             NULL AS late_interest_rate,
             NULL AS wallet_id
        FROM deposit_positions
        UNION ALL
        SELECT global_position_id,
               'FACTORING' AS product_type,
               name AS asset_key,
               NULL AS portfolio_name,
               NULL AS equity_type,
               currency,
               amount AS market_value,
               NULL AS quantity,
               NULL AS quantity_unit,
               NULL AS commodity_type,
               NULL AS weight,
               NULL AS weight_unit,
               amount AS cost_basis,
               interest_rate,
               start AS start_date,
               maturity,
               NULL AS extended_maturity,
               NULL AS extended_interest_rate,
             late_interest_rate,
             NULL AS wallet_id
        FROM factoring_positions
        UNION ALL
        SELECT global_position_id,
               'REAL_ESTATE_CF' AS product_type,
               name AS asset_key,
               NULL AS portfolio_name,
               NULL AS equity_type,
               currency,
               pending_amount AS market_value,
               NULL AS quantity,
               NULL AS quantity_unit,
               NULL AS commodity_type,
               NULL AS weight,
               NULL AS weight_unit,
               pending_amount AS cost_basis,
               interest_rate,
               start AS start_date,
               maturity,
               extended_maturity,
               extended_interest_rate,
             NULL AS late_interest_rate,
             NULL AS wallet_id
        FROM real_estate_cf_positions
    """

    GET_FLOWS_BASE = """
        SELECT it.entity_id,
               COALESCE(it.entity_account_id, '') AS ea_key,
               it.source,
               it.product_type,
               it.type,
               it.date,
               it.name AS asset_name,
               it.amount,
               it.currency,
               it.shares AS quantity,
               it.net_amount,
               COALESCE(it.fees, '0') AS fees,
               COALESCE(it.retentions, '0') AS retentions,
               CASE
                   WHEN it.product_type = 'STOCK_ETF' THEN
                       COALESCE(NULLIF(it.isin, ''), NULLIF(it.ticker, ''), it.name)
                   WHEN it.product_type = 'FUND' THEN
                       COALESCE(NULLIF(it.isin, ''), it.name)
                   WHEN it.product_type = 'CRYPTO' THEN
                       COALESCE(NULLIF(it.asset_contract_address, ''), NULLIF(it.ticker, ''), it.name)
                   WHEN it.product_type = 'DEPOSIT' THEN (
                       SELECT 'DEPOSIT:' || substr(d.creation, 1, 10) || ':' || d.maturity || ':' || d.amount || ':' || d.currency
                       FROM deposit_positions d
                           JOIN global_positions dgp ON dgp.id = d.global_position_id
                       WHERE dgp.entity_id = it.entity_id
                         AND COALESCE(dgp.entity_account_id, '') = COALESCE(it.entity_account_id, '')
                         AND d.currency = it.currency
                         AND (
                             (
                                 it.type = 'INVESTMENT'
                                 AND substr(d.creation, 1, 10) = substr(it.date, 1, 10)
                             )
                             OR (
                                 it.type = 'REPAYMENT'
                                 AND d.maturity = substr(it.date, 1, 10)
                             )
                             OR (
                                 it.type = 'INTEREST'
                                 AND d.maturity = substr(it.date, 1, 10)
                             )
                         )
                                               ORDER BY dgp.date ASC
                       LIMIT 1
                   )
                   ELSE it.name
               END AS asset_key,
               CASE
                   WHEN it.product_type = 'FUND' THEN COALESCE(
                       NULLIF(it.portfolio_name, ''),
                       (
                           SELECT p.name
                           FROM fund_positions f
                               JOIN global_positions gp ON gp.id = f.global_position_id
                               LEFT JOIN fund_portfolios p ON p.id = f.portfolio_id
                           WHERE gp.entity_id = it.entity_id
                             AND COALESCE(gp.entity_account_id, '') = COALESCE(it.entity_account_id, '')
                             AND gp.source = it.source
                             AND COALESCE(NULLIF(f.isin, ''), f.name) = COALESCE(NULLIF(it.isin, ''), it.name)
                                                         AND gp.date >= it.date
                                                     ORDER BY gp.date ASC
                                                     LIMIT 1
                                             ),
                                             (
                                                     SELECT p.name
                                                     FROM fund_positions f
                                                             JOIN global_positions gp ON gp.id = f.global_position_id
                                                             LEFT JOIN fund_portfolios p ON p.id = f.portfolio_id
                                                     WHERE gp.entity_id = it.entity_id
                                                         AND COALESCE(gp.entity_account_id, '') = COALESCE(it.entity_account_id, '')
                                                         AND gp.source = it.source
                                                         AND COALESCE(NULLIF(f.isin, ''), f.name) = COALESCE(NULLIF(it.isin, ''), it.name)
                                                         AND gp.date < it.date
                                                     ORDER BY gp.date DESC
                           LIMIT 1
                       )
                   )
               END AS portfolio_name,
               CASE
                   WHEN it.product_type = 'STOCK_ETF' THEN COALESCE(
                       CASE
                           WHEN it.product_subtype IN ('STOCK', 'ETF') THEN it.product_subtype
                       END,
                       (
                           SELECT CASE
                               WHEN s.type IN ('STOCK', 'ETF') THEN s.type
                           END
                           FROM stock_positions s
                               JOIN global_positions gp ON gp.id = s.global_position_id
                           WHERE gp.entity_id = it.entity_id
                             AND COALESCE(gp.entity_account_id, '') = COALESCE(it.entity_account_id, '')
                             AND gp.source = it.source
                             AND COALESCE(NULLIF(s.isin, ''), NULLIF(s.ticker, ''), s.name) = COALESCE(NULLIF(it.isin, ''), NULLIF(it.ticker, ''), it.name)
                                                         AND gp.date >= it.date
                                                     ORDER BY gp.date ASC
                                                     LIMIT 1
                                             ),
                                             (
                                                     SELECT CASE
                                                             WHEN s.type IN ('STOCK', 'ETF') THEN s.type
                                                     END
                                                     FROM stock_positions s
                                                             JOIN global_positions gp ON gp.id = s.global_position_id
                                                     WHERE gp.entity_id = it.entity_id
                                                         AND COALESCE(gp.entity_account_id, '') = COALESCE(it.entity_account_id, '')
                                                         AND gp.source = it.source
                                                         AND COALESCE(NULLIF(s.isin, ''), NULLIF(s.ticker, ''), s.name) = COALESCE(NULLIF(it.isin, ''), NULLIF(it.ticker, ''), it.name)
                                                     ORDER BY gp.date DESC
                           LIMIT 1
                       )
                   )
               END AS equity_type
        FROM investment_transactions it
    """

    GET_SETTLEMENTS_BASE = """
        SELECT h.entity_id,
               COALESCE(h.entity_account_id, '') AS ea_key,
               h.source,
               h.product_type,
               h.name AS asset_key,
               COALESCE(h.effective_maturity, h.last_tx_date) AS date,
               h.currency,
               COALESCE(
                   h.returned,
                   COALESCE(h.repaid, '0') + COALESCE(h.interests, '0')
               ) - COALESCE(h.fees, '0') - COALESCE(h.retentions, '0') AS net_proceeds
        FROM investment_historic h
        WHERE h.state IN ('COMPLETED', 'DEFAULTED')
          AND NOT EXISTS (
              SELECT 1
              FROM investment_historic_txs ht
                  JOIN investment_transactions it ON it.id = ht.tx_id
              WHERE ht.historic_entry_id = h.id
                AND (
                    it.type IN ('REPAYMENT', 'INTEREST')
                    OR it.ref LIKE 'manual-settlement-%'
                )
          )
    """

    GET_DATA_VERSION = """
        SELECT value
        FROM sys_config
        WHERE key = 'last_update'
    """
