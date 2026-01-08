export enum TransactionQueries {
  INSERT_INVESTMENT = `
        INSERT INTO investment_transactions (id, ref, name, amount, currency, type, date,
                                             entity_id, is_real, source, product_type, created_at,
                                             isin, ticker, market, shares, price, net_amount,
                                             fees, retentions, order_date, linked_tx, interests,
                                             iban, portfolio_name, product_subtype, asset_contract_address)
        VALUES (:id, :ref, :name, :amount, :currency, :type, :date,
                :entity_id, :is_real, :source, :product_type, :created_at,
                :isin, :ticker, :market, :shares, :price, :net_amount,
                :fees, :retentions, :order_date, :linked_tx, :interests,
                :iban, :portfolio_name, :product_subtype, :asset_contract_address)
    `,
  INSERT_ACCOUNT = `
        INSERT INTO account_transactions (id, ref, name, amount, currency, type, date,
                                          entity_id, is_real, source, created_at,
                                          fees, retentions, interest_rate, avg_balance, net_amount)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `,
  INVESTMENT_SELECT_BASE = `
        SELECT it.*,
               e.id         AS entity_id,
               e.name       AS entity_name,
               e.type       as entity_type,
               e.origin     as entity_origin,
               e.natural_id AS entity_natural_id,
               e.icon_url   AS icon_url
        FROM investment_transactions it
            JOIN entities e ON it.entity_id = e.id
    `,
  ACCOUNT_SELECT_BASE = `
        SELECT at.*,
               e.id         AS entity_id,
               e.name       AS entity_name,
               e.natural_id AS entity_natural_id,
               e.type       as entity_type,
               e.origin     as entity_origin,
               e.icon_url   AS icon_url
        FROM account_transactions at
            JOIN entities e ON at.entity_id = e.id
    `,
  INVESTMENT_SELECT_BY_ENTITY = `
        SELECT it.*,
               e.name       AS entity_name,
               e.id         AS entity_id,
               e.type       as entity_type,
               e.origin     AS entity_origin,
               e.natural_id AS entity_natural_id,
               e.icon_url   AS icon_url
        FROM investment_transactions it
            JOIN entities e ON it.entity_id = e.id
        WHERE it.entity_id = ?
    `,
  ACCOUNT_SELECT_BY_ENTITY = `
        SELECT at.*,
               e.id         AS entity_id,
               e.name       AS entity_name,
               e.natural_id AS entity_natural_id,
               e.type       AS entity_type,
               e.origin     AS entity_origin,
               e.icon_url   AS icon_url
        FROM account_transactions at
            JOIN entities e ON at.entity_id = e.id
        WHERE at.entity_id = ?
    `,
  GET_REFS_BY_ENTITY = `
        SELECT ref
        FROM investment_transactions
        WHERE entity_id = ?
        UNION
        SELECT ref
        FROM account_transactions
        WHERE entity_id = ?
    `,
  INVESTMENT_AND_ACCOUNT_BY_ENTITY_AND_SOURCE = `
        SELECT it.*,
               e.name       AS entity_name,
               e.id         AS entity_id,
               e.type       as entity_type,
               e.origin     AS entity_origin,
               e.natural_id AS entity_natural_id,
               e.icon_url   AS icon_url
        FROM investment_transactions it
            JOIN entities e ON it.entity_id = e.id
        WHERE it.entity_id = ? AND it.source = ?
    `,
  ACCOUNT_BY_ENTITY_AND_SOURCE = `
        SELECT at.*,
               e.id         AS entity_id,
               e.name       AS entity_name,
               e.natural_id AS entity_natural_id,
               e.type       AS entity_type,
               e.origin     AS entity_origin,
               e.icon_url   AS icon_url
        FROM account_transactions at
            JOIN entities e ON at.entity_id = e.id
        WHERE at.entity_id = ? AND at.source = ?
    `,
  GET_REFS_BY_SOURCE_TYPE = `
        SELECT ref
        FROM investment_transactions
        WHERE is_real = ?
        UNION
        SELECT ref
        FROM account_transactions
        WHERE is_real = ?
    `,
  GET_BY_FILTERS_BASE = `
        SELECT tx.*,
               e.name       AS entity_name,
               e.type       as entity_type,
               e.origin     as entity_origin,
               e.natural_id as entity_natural_id,
               e.icon_url   AS icon_url
        FROM (
            SELECT id,
                   ref,
                   name,
                   amount,
                   currency,
                   type,
                   date,
                   entity_id,
                   is_real,
                   source,
                   product_type,
                   fees,
                   retentions,
                   NULL AS interest_rate,
                   NULL AS avg_balance,
                   isin,
                   ticker,
                   asset_contract_address,
                   market,
                   shares,
                   price,
                   net_amount,
                   order_date,
                   linked_tx,
                   interests,
                   iban,
                   portfolio_name,
                   product_subtype
            FROM investment_transactions
            UNION ALL
            SELECT id,
                   ref,
                   name,
                   amount,
                   currency,
                   type,
                   date,
                   entity_id,
                   is_real,
                   source,
                   'ACCOUNT' AS product_type,
                   fees,
                   retentions,
                   interest_rate,
                   avg_balance,
                   NULL      AS isin,
                   NULL      AS ticker,
                   NULL      AS asset_contract_address,
                   NULL      AS market,
                   NULL      AS shares,
                   NULL      AS price,
                   net_amount,
                   NULL      AS order_date,
                   NULL      AS linked_tx,
                   NULL      AS interests,
                   NULL      AS iban,
                   NULL      AS portfolio_name,
                   NULL      AS product_subtype
            FROM account_transactions
        ) tx
            JOIN entities e ON tx.entity_id = e.id
    `,
  DELETE_INVESTMENT_BY_SOURCE = "DELETE FROM investment_transactions WHERE source = ?",
  DELETE_ACCOUNT_BY_SOURCE = "DELETE FROM account_transactions WHERE source = ?",
  DELETE_INVESTMENT_BY_ENTITY_SOURCE = "DELETE FROM investment_transactions WHERE entity_id = ? AND source = ?",
  DELETE_ACCOUNT_BY_ENTITY_SOURCE = "DELETE FROM account_transactions WHERE entity_id = ? AND source = ?",
  GET_INVESTMENT_BY_ID = `
        SELECT it.*,
               e.id         AS entity_id,
               e.name       AS entity_name,
               e.type       AS entity_type,
               e.origin     AS entity_origin,
               e.natural_id AS entity_natural_id,
               e.icon_url   AS icon_url
        FROM investment_transactions it
            JOIN entities e ON it.entity_id = e.id
        WHERE it.id = ?
    `,
  GET_ACCOUNT_BY_ID = `
        SELECT at.*,
               e.id         AS entity_id,
               e.name       AS entity_name,
               e.type       AS entity_type,
               e.origin     AS entity_origin,
               e.natural_id AS entity_natural_id,
               e.icon_url   AS icon_url
        FROM account_transactions at
            JOIN entities e ON at.entity_id = e.id
        WHERE at.id = ?
    `,
  DELETE_BY_ID_INVESTMENT = "DELETE FROM investment_transactions WHERE id = ?",
  DELETE_BY_ID_ACCOUNT = "DELETE FROM account_transactions WHERE id = ?",
}
