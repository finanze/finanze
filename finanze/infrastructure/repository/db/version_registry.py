from infrastructure.repository.db.versions.v0_genesis import V0Genesis
from infrastructure.repository.db.versions.v011_0 import V0110
from infrastructure.repository.db.versions.v020_0_crypto import V0200Crypto
from infrastructure.repository.db.versions.v020_1_fetches import V0201
from infrastructure.repository.db.versions.v020_2_null_portfolio_kpis import V0202
from infrastructure.repository.db.versions.v020_3_virtual_imports_feature import V0203
from infrastructure.repository.db.versions.v020_4_commodities import V0204Commodities
from infrastructure.repository.db.versions.v020_5_recf_rename import V0205
from infrastructure.repository.db.versions.v030_0_integrations import V0300Integrations
from infrastructure.repository.db.versions.v030_1_bsc import V0301BSC
from infrastructure.repository.db.versions.v030_2_re_rename_historic import V0302
from infrastructure.repository.db.versions.v030_3_crypto_initial_investments import (
    V0303CryptoInitialInvestments,
)
from infrastructure.repository.db.versions.v040_0_earnings_expenses import (
    V0400EarningsExpenses,
)
from infrastructure.repository.db.versions.v040_1_more_loan_details import V0401

versions = [
    V0Genesis(),
    V0110(),
    V0200Crypto(),
    V0201(),
    V0202(),
    V0203(),
    V0204Commodities(),
    V0205(),
    V0300Integrations(),
    V0301BSC(),
    V0302(),
    V0303CryptoInitialInvestments(),
    V0400EarningsExpenses(),
    V0401(),
]
