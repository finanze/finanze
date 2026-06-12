from enum import Enum


class NetworthTimelineQueries(str, Enum):
    GET_POINTS_BASE = """
        SELECT date, currency, total, breakdown
        FROM networth_timeline_points
    """

    GET_STATE = """
        SELECT inputs_signature, last_computed_date
        FROM networth_timeline_meta
        WHERE id = 1
    """

    DELETE_ALL_POINTS = "DELETE FROM networth_timeline_points"

    UPSERT_POINT = """
        INSERT OR REPLACE INTO networth_timeline_points (date, currency, total, breakdown)
        VALUES (?, ?, ?, ?)
    """

    UPSERT_STATE = """
        INSERT OR REPLACE INTO networth_timeline_meta (id, inputs_signature, last_computed_date)
        VALUES (1, ?, ?)
    """

    GET_SNAPSHOTS_BASE = """
        SELECT gp.id, gp.entity_id, COALESCE(gp.entity_account_id, '') AS ea_key,
               gp.source, gp.date, ea.deleted_at
        FROM global_positions gp
            LEFT JOIN entity_accounts ea ON gp.entity_account_id = ea.id
        WHERE gp.source = 'REAL'
    """

    GET_BATCHED_IMPORTS = """
        SELECT gp.source AS source,
               vdi.import_id AS import_id,
               vdi.date AS import_date,
               vdi.global_position_id AS gp_id
        FROM virtual_data_imports vdi
            JOIN global_positions gp ON gp.id = vdi.global_position_id
        WHERE vdi.feature = 'POSITION'
          AND vdi.global_position_id IS NOT NULL
          AND gp.source IN ('MANUAL', 'SHEETS')
    """

    GET_HOLDING_VALUATIONS = """
        SELECT global_position_id, 'ACCOUNT' AS product_type, currency, total AS amount, NULL AS loan_ref,
               NULL AS commodity_type, NULL AS weight, NULL AS weight_unit FROM account_positions
        UNION ALL
        SELECT global_position_id, 'STOCK_ETF', currency, market_value, NULL, NULL, NULL, NULL FROM stock_positions
        UNION ALL
        SELECT global_position_id, 'FUND', currency, market_value, NULL, NULL, NULL, NULL FROM fund_positions
        UNION ALL
        SELECT global_position_id, 'DEPOSIT', currency, amount, NULL, NULL, NULL, NULL FROM deposit_positions
        UNION ALL
        SELECT global_position_id, 'FACTORING', currency, amount, NULL, NULL, NULL, NULL FROM factoring_positions
        UNION ALL
        SELECT global_position_id, 'REAL_ESTATE_CF', currency, amount, NULL, NULL, NULL, NULL FROM real_estate_cf_positions
        UNION ALL
        SELECT global_position_id, 'CROWDLENDING', currency, total, NULL, NULL, NULL, NULL FROM crowdlending_positions
        UNION ALL
        SELECT global_position_id, 'CRYPTO', currency, market_value, NULL, NULL, NULL, NULL FROM crypto_currency_positions
        UNION ALL
        SELECT global_position_id, 'COMMODITY', currency, market_value, NULL, type, amount, unit FROM commodity_positions
        UNION ALL
        SELECT global_position_id, 'DERIVATIVE', currency, market_value, NULL, NULL, NULL, NULL FROM derivative_positions
        UNION ALL
        SELECT global_position_id, 'CARD', currency, used, NULL, NULL, NULL, NULL FROM card_positions
        UNION ALL
        SELECT global_position_id, 'LOAN', currency, principal_outstanding, hash, NULL, NULL, NULL FROM loan_positions
        UNION ALL
        SELECT global_position_id, 'CREDIT', currency, drawn_amount, NULL, NULL, NULL, NULL FROM credit_positions
    """

    GET_MORTGAGE_VALUATIONS = """
        SELECT gp.date AS date,
               lp.hash AS loan_ref,
               lp.principal_outstanding AS outstanding,
               lp.currency AS currency,
               lp.creation AS origination
        FROM loan_positions lp
            JOIN global_positions gp ON lp.global_position_id = gp.id
        WHERE lp.hash IN ({placeholders})
        ORDER BY gp.date ASC
    """
