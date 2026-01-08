export enum ManualPositionDataQueries {
  INSERT = `
        INSERT INTO manual_position_data (
            entry_id, global_position_id, product_type, track_ticker, tracker_key
        )
        VALUES (?, ?, ?, ?, ?)
    `,
  GET_TRACKABLE = `
        SELECT entry_id, global_position_id, product_type, tracker_key
        FROM manual_position_data
        WHERE track_ticker = 1 AND tracker_key IS NOT NULL
    `,
  DELETE_BY_POSITION_ID_AND_TYPE = "DELETE FROM manual_position_data WHERE global_position_id = ? AND product_type = ?",
}

export enum PositionWriteQueries {
  INSERT_LOAN_POSITION = `
        INSERT INTO loan_positions (id, global_position_id, type, currency, name, current_installment,
                                    interest_rate, interest_type, loan_amount, next_payment_date,
                                    principal_outstanding, principal_paid, euribor_rate, fixed_years,
                                    creation, maturity, unpaid)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `,
  INSERT_CARD_POSITION = `
        INSERT INTO card_positions (id, global_position_id, type, name, currency,
                                    ending, card_limit, used, active, related_account)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `,
  INSERT_ACCOUNT_POSITION = `
        INSERT INTO account_positions (id, global_position_id, type, currency, name, iban, total,
                                       interest, retained, pending_transfers)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `,
  INSERT_CROWDLENDING_POSITION = `
        INSERT INTO crowdlending_positions (id, global_position_id, total, weighted_interest_rate, currency,
                                            distribution)
        VALUES (?, ?, ?, ?, ?, ?)
    `,
  INSERT_COMMODITY_POSITION = `
        INSERT INTO commodity_positions (id, global_position_id, name, type, amount, unit,
                                         market_value, currency, initial_investment, average_buy_price)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `,
  INSERT_CRYPTO_CURRENCY_POSITION = `
        INSERT INTO crypto_currency_positions (id, global_position_id, wallet_id, name, symbol, type, amount,
                                               market_value, currency, contract_address, crypto_asset_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `,
  INSERT_CRYPTO_CURRENCY_INITIAL_INVESTMENT = `
        INSERT INTO crypto_currency_initial_investments (id, crypto_currency_position, currency,
                                                         initial_investment, average_buy_price)
        VALUES (?, ?, ?, ?, ?)
    `,
  INSERT_DEPOSIT_POSITION = `
        INSERT INTO deposit_positions (id, global_position_id, name, amount, currency,
                                       expected_interests, interest_rate, creation, maturity)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    `,
  INSERT_REAL_ESTATE_CF_POSITION = `
        INSERT INTO real_estate_cf_positions (id, global_position_id, name, amount, pending_amount, currency,
                                              interest_rate, profitability, last_invest_date, start, maturity, type,
                                              business_type, state, extended_maturity, extended_interest_rate)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `,
  INSERT_FACTORING_POSITION = `
        INSERT INTO factoring_positions (id, global_position_id, name, amount, currency,
                                         interest_rate, profitability, gross_interest_rate, late_interest_rate,
                                         gross_late_interest_rate, last_invest_date, start, maturity, type, state)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `,
  INSERT_FUND_PORTFOLIO = `
        INSERT INTO fund_portfolios (id, global_position_id, name, currency, initial_investment, market_value,
                                     account_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    `,
  INSERT_FUND_POSITION = `
        INSERT INTO fund_positions (id, global_position_id, name, isin, market,
                                    shares, initial_investment, average_buy_price,
                                    market_value, type, asset_type, currency, portfolio_id, info_sheet_url)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `,
  INSERT_STOCK_POSITION = `
        INSERT INTO stock_positions (id, global_position_id, name, ticker, isin, market,
                                     shares, initial_investment, average_buy_price,
                                     market_value, currency, type, subtype, info_sheet_url)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `,
}

export enum PositionQueries {
  INSERT_GLOBAL_POSITION = "INSERT INTO global_positions (id, date, entity_id, source) VALUES (?, ?, ?, ?)",
  REAL_GROUPED_BY_ENTITY_BASE = `
        WITH latest_positions AS (
            SELECT entity_id, MAX(date) as latest_date
            FROM global_positions
            WHERE source = 'REAL'
            GROUP BY entity_id
        )
        SELECT gp.*,
               e.id         AS entity_id,
               e.name       AS entity_name,
               e.natural_id AS entity_natural_id,
               e.type       as entity_type,
               e.origin     as entity_origin,
               e.icon_url   as icon_url
        FROM global_positions gp
            JOIN latest_positions lp ON gp.entity_id = lp.entity_id AND gp.date = lp.latest_date
            JOIN entities e ON gp.entity_id = e.id
        WHERE gp.source = 'REAL'
    `,
  NON_REAL_GROUPED_BY_ENTITY_BASE = `
        WITH latest_import_details AS (
            SELECT vdi.import_id
            FROM virtual_data_imports vdi
                JOIN (
                    SELECT source, MAX(date) AS max_date
                    FROM virtual_data_imports
                    GROUP BY source
                ) mx ON mx.source = vdi.source AND mx.max_date = vdi.date
            GROUP BY vdi.source
        ),
        last_imported_position_ids AS (
            SELECT vdi.global_position_id
            FROM virtual_data_imports vdi
                JOIN latest_import_details lid ON vdi.import_id = lid.import_id
            WHERE vdi.global_position_id IS NOT NULL
        )
        SELECT gp.*,
               e.name       AS entity_name,
               e.id         AS entity_id,
               e.natural_id AS entity_natural_id,
               e.type       AS entity_type,
               e.origin     AS entity_origin,
               e.icon_url   AS icon_url
        FROM global_positions gp
            JOIN last_imported_position_ids lp ON gp.id = lp.global_position_id
            JOIN entities e ON gp.entity_id = e.id
    `,
  GET_ACCOUNTS_BY_GLOBAL_POSITION_ID = `
        SELECT *
        FROM account_positions
        WHERE global_position_id = ?
    `,
  GET_CARDS_BY_GLOBAL_POSITION_ID = "SELECT * FROM card_positions WHERE global_position_id = ?",
  GET_LOANS_BY_GLOBAL_POSITION_ID = "SELECT * FROM loan_positions WHERE global_position_id = ?",
  GET_STOCKS_BY_GLOBAL_POSITION_ID = "SELECT * FROM stock_positions s LEFT JOIN manual_position_data mpd ON mpd.entry_id = s.id WHERE s.global_position_id = ?",
  GET_FUND_PORTFOLIOS_BY_GLOBAL_POSITION_ID = `
        SELECT fp.*, ap.id AS account_id, ap.total, ap.name as account_name, ap.iban
        FROM fund_portfolios fp
            LEFT JOIN account_positions ap ON fp.account_id = ap.id
        WHERE fp.global_position_id = ?
    `,
  GET_FUNDS_BY_GLOBAL_POSITION_ID = `
        SELECT f.*,
               mpd.*,
               p.id                 AS portfolio_id,
               p.name               AS portfolio_name,
               p.currency           AS portfolio_currency,
               p.initial_investment AS portfolio_investment,
               p.market_value       AS portfolio_value
        FROM fund_positions f
            LEFT JOIN fund_portfolios p ON p.id = f.portfolio_id
            LEFT JOIN manual_position_data mpd ON mpd.entry_id = f.id
        WHERE f.global_position_id = ?
    `,
  GET_FACTORING_BY_GLOBAL_POSITION_ID = "SELECT * FROM factoring_positions WHERE global_position_id = ?",
  GET_REAL_ESTATE_CF_BY_GLOBAL_POSITION_ID = "SELECT * FROM real_estate_cf_positions WHERE global_position_id = ?",
  GET_DEPOSITS_BY_GLOBAL_POSITION_ID = "SELECT * FROM deposit_positions WHERE global_position_id = ?",
  GET_CROWDLENDING_BY_GLOBAL_POSITION_ID = "SELECT * FROM crowdlending_positions WHERE global_position_id = ?",
  GET_CRYPTO_BY_GLOBAL_POSITION_ID = `
        SELECT p.*,
               a.*,
               a.name     as asset_name,
               c.address,
               c.name     AS wallet_name,
               i.initial_investment,
               i.average_buy_price,
               i.currency as investment_currency
        FROM crypto_currency_positions p
            LEFT JOIN crypto_currency_initial_investments i ON p.id = i.crypto_currency_position
            LEFT JOIN crypto_assets a ON p.crypto_asset_id = a.id
            LEFT JOIN crypto_wallet_connections c ON p.wallet_id = c.id
        WHERE global_position_id = ?
    `,
  GET_COMMODITIES_BY_GLOBAL_POSITION_ID = "SELECT * FROM commodity_positions WHERE global_position_id = ?",
  GET_ENTITY_ID_FROM_GLOBAL_POSITION_ID = "SELECT entity_id FROM global_positions WHERE id = ?",
  DELETE_POSITION_FOR_DATE = `
        DELETE
        FROM global_positions
        WHERE entity_id = ?
          AND DATE(date) = ?
          AND source = ?
    `,
  GET_GLOBAL_POSITION_BY_ID = `
        SELECT gp.*,
               e.id         AS entity_id,
               e.name       AS entity_name,
               e.natural_id AS entity_natural_id,
               e.type       AS entity_type,
               e.origin     AS entity_origin,
               e.icon_url   AS icon_url
        FROM global_positions gp
            JOIN entities e ON gp.entity_id = e.id
        WHERE gp.id = ?
    `,
  DELETE_GLOBAL_POSITION_BY_ID = "DELETE FROM global_positions WHERE id = ?",
  GET_STOCK_DETAIL = `
        SELECT s.*, gp.source
        FROM stock_positions s
            JOIN global_positions gp ON gp.id = s.global_position_id
        WHERE s.id = ?
    `,
  GET_FUND_DETAIL = `
        SELECT f.*, gp.source
        FROM fund_positions f
            JOIN global_positions gp ON gp.id = f.global_position_id
        WHERE f.id = ?
    `,
  UPDATE_STOCK_MARKET_VALUE = "UPDATE stock_positions SET market_value = ? WHERE id = ?",
  UPDATE_FUND_MARKET_VALUE = "UPDATE fund_positions SET market_value = ? WHERE id = ?",
}
