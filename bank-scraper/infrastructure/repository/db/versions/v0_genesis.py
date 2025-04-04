from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.upgrader import DBVersionMigration

DDL = """

-- FINANCIAL ENTITY

CREATE TABLE financial_entities (
    id INTEGER PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    features JSON NOT NULL,
    properties JSON NOT NULL,
    is_real BOOLEAN NOT NULL
);

-- POSITION

CREATE TABLE global_positions (
    id CHAR(36) PRIMARY KEY,
    date DATETIME NOT NULL,
    entity_id INTEGER NOT NULL REFERENCES financial_entities(id) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE INDEX idx_gp_entity_id ON global_positions(entity_id);
CREATE INDEX idx_global_positions_date ON global_positions(date DESC);

CREATE TABLE account_positions (
    id CHAR(36) PRIMARY KEY,
    global_position_id CHAR(36) REFERENCES global_positions(id),
    type VARCHAR(32) NOT NULL,
    name TEXT,
    iban VARCHAR(32),
    total TEXT NOT NULL,
    interest TEXT NOT NULL,
    retained TEXT,
    pending_transfers TEXT
);

CREATE INDEX idx_ap_global_position_id ON account_positions(global_position_id);

CREATE TABLE card_positions (
    id CHAR(36) PRIMARY KEY,
    global_position_id CHAR(36) REFERENCES global_positions(id) ON DELETE CASCADE ON UPDATE CASCADE,
    type VARCHAR(32) NOT NULL,
    name TEXT,
    ending TEXT,
    card_limit TEXT,
    used TEXT,
    related_account CHAR(36) REFERENCES account_positions(id) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE INDEX idx_cp_global_position_id ON card_positions(global_position_id);

CREATE TABLE mortgage_positions (
    id CHAR(36) PRIMARY KEY,
    global_position_id CHAR(36) REFERENCES global_positions(id) ON DELETE CASCADE ON UPDATE CASCADE,
    name TEXT,
    current_installment TEXT NOT NULL,
    interest_rate TEXT NOT NULL,
    loan_amount TEXT,
    next_payment_date DATE NOT NULL,
    principal_outstanding TEXT NOT NULL,
    principal_paid TEXT NOT NULL
);

CREATE INDEX idx_mp_global_position_id ON mortgage_positions(global_position_id);

-- - Latest investment position KPIs

CREATE TABLE latest_investment_position_kpis (
    entity_id INTEGER NOT NULL REFERENCES financial_entities(id),
    investment_type VARCHAR(32) NOT NULL,
    metric VARCHAR(64) NOT NULL,
    value TEXT NOT NULL,
    last_updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    global_position_id CHAR(36) NOT NULL REFERENCES global_positions(id),
    PRIMARY KEY (entity_id, investment_type, metric)
);

CREATE INDEX idx_ikpis_global_position_id ON latest_investment_position_kpis(global_position_id);
CREATE INDEX idx_ikpis_entity_type_metric ON latest_investment_position_kpis(entity_id, investment_type, metric);

CREATE TABLE stock_positions (
    id CHAR(36) PRIMARY KEY,
    global_position_id CHAR(36) REFERENCES global_positions(id) ON DELETE CASCADE ON UPDATE CASCADE,
    name TEXT NOT NULL,
    ticker VARCHAR(16) NOT NULL,
    isin VARCHAR(12) NOT NULL,
    market VARCHAR(50) NOT NULL,
    shares TEXT NOT NULL,
    initial_investment TEXT NOT NULL,
    average_buy_price TEXT NOT NULL,
    market_value TEXT NOT NULL,
    currency CHAR(3) NOT NULL,
    type VARCHAR(32) NOT NULL,
    subtype VARCHAR(32)
);

CREATE INDEX idx_sp_global_position_id ON stock_positions(global_position_id);

CREATE TABLE fund_positions (
    id CHAR(36) PRIMARY KEY,
    global_position_id CHAR(36) REFERENCES global_positions(id) ON DELETE CASCADE ON UPDATE CASCADE,
    name TEXT NOT NULL,
    isin VARCHAR(12) NOT NULL,
    market VARCHAR(50) NOT NULL,
    shares TEXT NOT NULL,
    initial_investment TEXT NOT NULL,
    average_buy_price TEXT NOT NULL,
    market_value TEXT NOT NULL,
    currency CHAR(3) NOT NULL
);

CREATE INDEX idx_fp_global_position_id ON fund_positions(global_position_id);

CREATE TABLE factoring_positions (
    id CHAR(36) PRIMARY KEY,
    global_position_id CHAR(36) REFERENCES global_positions(id) ON DELETE CASCADE ON UPDATE CASCADE,
    name TEXT NOT NULL,
    amount TEXT NOT NULL,
    currency CHAR(3) NOT NULL,
    interest_rate TEXT NOT NULL,
    net_interest_rate TEXT NOT NULL,
    last_invest_date DATETIME,
    maturity DATE NOT NULL,
    type VARCHAR(32) NOT NULL,
    state VARCHAR(32) NOT NULL
);

CREATE INDEX idx_facp_global_position_id ON factoring_positions(global_position_id);

CREATE TABLE real_state_cf_positions (
    id CHAR(36) PRIMARY KEY,
    global_position_id CHAR(36) REFERENCES global_positions(id) ON DELETE CASCADE ON UPDATE CASCADE,
    name TEXT NOT NULL,
    amount TEXT NOT NULL,
    currency CHAR(3) NOT NULL,
    interest_rate TEXT NOT NULL,
    last_invest_date DATETIME,
    months INTEGER NOT NULL,
    type VARCHAR(32) NOT NULL,
    business_type VARCHAR(32) NOT NULL,
    state VARCHAR(32),
    potential_extension INTEGER
);

CREATE INDEX idx_rscfp_global_position_id ON real_state_cf_positions(global_position_id);

CREATE TABLE deposit_positions (
    id CHAR(36) PRIMARY KEY,
    global_position_id CHAR(36) REFERENCES global_positions(id) ON DELETE CASCADE ON UPDATE CASCADE,
    name TEXT NOT NULL,
    amount TEXT NOT NULL,
    total_interests TEXT NOT NULL,
    interest_rate TEXT NOT NULL,
    creation DATETIME NOT NULL,
    maturity DATE NOT NULL
);

CREATE INDEX idx_dp_global_position_id ON deposit_positions(global_position_id);

CREATE TABLE crowdlending_positions (
    id CHAR(36) PRIMARY KEY,
    global_position_id CHAR(36) REFERENCES global_positions(id) ON DELETE CASCADE ON UPDATE CASCADE,
    distribution JSON NOT NULL
);

CREATE INDEX idx_clp_global_position_id ON crowdlending_positions(global_position_id);

-- CONTRIBUTIONS

CREATE TABLE periodic_contributions (
    id CHAR(36) NOT NULL PRIMARY KEY,
    entity_id INTEGER NOT NULL REFERENCES financial_entities(id) ON DELETE CASCADE ON UPDATE CASCADE,
    isin VARCHAR(12) NOT NULL,
    alias VARCHAR(100),
    amount TEXT NOT NULL,
    currency CHAR(3) NOT NULL,
    since DATE NOT NULL,
    until DATE,
    frequency VARCHAR(32) NOT NULL,
    active BOOLEAN NOT NULL,
    is_real BOOLEAN NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_pcont_entity_isin ON periodic_contributions(entity_id, isin);

-- TRANSACTIONS

CREATE TABLE investment_transactions (
    id CHAR(36) NOT NULL PRIMARY KEY,
    ref TEXT NOT NULL,
    name TEXT NOT NULL,
    amount TEXT NOT NULL,
    currency CHAR(3) NOT NULL,
    type VARCHAR(32) NOT NULL,
    date DATETIME NOT NULL,
    entity_id INTEGER NOT NULL REFERENCES financial_entities(id) ON DELETE CASCADE ON UPDATE CASCADE,
    is_real BOOLEAN NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    product_type VARCHAR(32),
    
    isin VARCHAR(12) DEFAULT NULL,
    market VARCHAR(32) DEFAULT NULL,
    order_date DATETIME DEFAULT NULL,
    linked_tx CHAR(36) DEFAULT NULL REFERENCES investment_transactions(id) ON DELETE RESTRICT ON UPDATE CASCADE,

    net_amount TEXT DEFAULT NULL,
    shares TEXT DEFAULT NULL,
    price TEXT DEFAULT NULL,
    fees TEXT DEFAULT NULL,
    retentions TEXT DEFAULT NULL,
    ticker VARCHAR(16) DEFAULT NULL,

    interests TEXT DEFAULT NULL
);

CREATE INDEX idx_itxs_investment_entity_id ON investment_transactions(entity_id);
CREATE INDEX idx_itxs_investment_date ON investment_transactions(date DESC);
CREATE INDEX idx_itxs_investment_isin ON investment_transactions(isin);
CREATE INDEX idx_itxs_investment_product_type ON investment_transactions(product_type);


CREATE TABLE account_transactions (
    id CHAR(36) NOT NULL PRIMARY KEY,
    ref TEXT NOT NULL,
    name TEXT NOT NULL,
    amount TEXT NOT NULL,
    currency CHAR(3) NOT NULL,
    type VARCHAR(32) NOT NULL,
    date DATETIME NOT NULL,
    entity_id INTEGER NOT NULL REFERENCES financial_entities(id) ON DELETE CASCADE ON UPDATE CASCADE,
    is_real BOOLEAN NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    
    interest_rate TEXT DEFAULT NULL,
    avg_balance TEXT DEFAULT NULL,
    fees TEXT DEFAULT NULL,
    retentions TEXT DEFAULT NULL
);

CREATE INDEX idx_account_entity_id ON account_transactions(entity_id);
CREATE INDEX idx_account_date ON account_transactions(date DESC);
CREATE INDEX idx_account_type ON account_transactions(type);
"""

INSERT_FINANCIAL_ENTITIES = """
INSERT INTO financial_entities (name, features, properties, is_real)
VALUES 
    (
        'MyInvestor', 
        json_array('POSITION', 'AUTO_CONTRIBUTIONS', 'TRANSACTIONS'), 
        json_object(),
        TRUE
    ),
    (
        'Unicaja', 
        json_array('POSITION'), 
        json_object(),
        TRUE
    ),
    (
        'Trade Republic', 
        json_array('POSITION', 'TRANSACTIONS'), 
        json_object('pin', json_object('positions', 4)),
        TRUE
    ),
    (
        'Urbanitae', 
        json_array('POSITION', 'TRANSACTIONS', 'HISTORIC'), 
        json_object(),
        TRUE
    ),
    (
        'Wecity', 
        json_array('POSITION', 'TRANSACTIONS', 'HISTORIC'), 
        json_object('pin', json_object('positions', 6)),
        TRUE
    ),
    (
        'SEGO', 
        json_array('POSITION', 'TRANSACTIONS', 'HISTORIC'), 
        json_object('pin', json_object('positions', 6)),
        TRUE
    ),
    (
        'Mintos', 
        json_array('POSITION'), 
        json_object(),
        TRUE
    ),
    (
        'Freedom24', 
        json_array('POSITION'), 
        json_object(),
        TRUE
    );
"""


class V0Genesis(DBVersionMigration):

    @property
    def name(self):
        return 'v0 Genesis'

    def upgrade(self, cursor: DBCursor):
        ddl_without_comments = '\n'.join(
            [line for line in DDL.split('\n') if not line.startswith('--') and line.strip() != ''])
        statements = [statement.strip() for statement in ddl_without_comments.split(';') if statement.strip()]
        for statement in statements:
            cursor.execute(statement)

        cursor.execute(INSERT_FINANCIAL_ENTITIES)
