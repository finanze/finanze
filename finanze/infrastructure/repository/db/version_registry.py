from infrastructure.repository.db.versions.v0.v00.v0_genesis import V0Genesis
from infrastructure.repository.db.versions.v0.v01.v011_0 import V0110
from infrastructure.repository.db.versions.v0.v02.v020_0_crypto import V0200Crypto
from infrastructure.repository.db.versions.v0.v02.v020_1_fetches import V0201
from infrastructure.repository.db.versions.v0.v02.v020_2_null_portfolio_kpis import (
    V0202,
)
from infrastructure.repository.db.versions.v0.v02.v020_3_virtual_imports_feature import (
    V0203,
)
from infrastructure.repository.db.versions.v0.v02.v020_4_commodities import (
    V0204Commodities,
)
from infrastructure.repository.db.versions.v0.v02.v020_5_recf_rename import V0205
from infrastructure.repository.db.versions.v0.v03.v030_0_integrations import (
    V0300Integrations,
)
from infrastructure.repository.db.versions.v0.v03.v030_1_bsc import V0301BSC
from infrastructure.repository.db.versions.v0.v03.v030_2_re_rename_historic import V0302
from infrastructure.repository.db.versions.v0.v03.v030_3_crypto_initial_investments import (
    V0303CryptoInitialInvestments,
)
from infrastructure.repository.db.versions.v0.v04.v040_0_earnings_expenses import (
    V0400EarningsExpenses,
)
from infrastructure.repository.db.versions.v0.v04.v040_1_more_loan_details import V0401
from infrastructure.repository.db.versions.v0.v04.v040_2_var_mixed_loans import V0402
from infrastructure.repository.db.versions.v0.v04.v040_3_add_account_tx_net_amount import (
    V0403,
)
from infrastructure.repository.db.versions.v0.v04.v040_4_real_estate import (
    V0404RealEstate,
)
from infrastructure.repository.db.versions.v0.v04.v040_5_flows_icon import (
    V0405FlowsIcon,
)
from infrastructure.repository.db.versions.v0.v04.v040_6_contrib_target_name import (
    V0406ContribTargetName,
)
from infrastructure.repository.db.versions.v0.v04.v040_7_recf_profitability import (
    V0407RECFProfitability,
)
from infrastructure.repository.db.versions.v0.v04.v040_8_add_fund_portfolio_account import (
    V0408FundPortfolioAccount,
)
from infrastructure.repository.db.versions.v0.v05.v050_0_ing import V0500ING
from infrastructure.repository.db.versions.v0.v05.v050_1_external_provider import (
    V0501ExternalEntityProvider,
)
from infrastructure.repository.db.versions.v0.v05.v050_2_loan_positions_optional_next_date import (
    V0502,
)
from infrastructure.repository.db.versions.v0.v05.v050_3_fund_portfolio_txs import (
    V0503FundPortfolioTxs,
)
from infrastructure.repository.db.versions.v0.v05.v050_4_fund_market_nullable import (
    V0504,
)
from infrastructure.repository.db.versions.v0.v05.v050_5_add_fund_asset_type import (
    V0505,
)
from infrastructure.repository.db.versions.v0.v06.v060_0_add_source_txs_contributions import (
    V0600Source,
)
from infrastructure.repository.db.versions.v0.v06.v060_1_recreate_position_tables import (
    V0601RecreatePositionTables,
)
from infrastructure.repository.db.versions.v0.v06.v060_2_use_source_positions import (
    V0602Source,
)
from infrastructure.repository.db.versions.v0.v06.v060_3_fund_etf_data_sheet_and_type import (
    V0603FundETFFields,
)
from infrastructure.repository.db.versions.v0.v06.v060_4_manual_position_data import (
    V0604ManualPositionData,
)
from infrastructure.repository.db.versions.v0.v06.v060_5_add_tx_product_subype import (
    V0605TxProductSubtype,
)
from infrastructure.repository.db.versions.v0.v06.v060_6_migrate_equity_types import (
    V0606,
)
from infrastructure.repository.db.versions.v0.v07.v070_0_add_contrib_target_subype import (
    V0700ContribTargetSubtype,
)
from infrastructure.repository.db.versions.v0.v07.v070_1_crypto_currencies_v2 import (
    V0701CryptoCurrenciesV2,
)
from infrastructure.repository.db.versions.v0.v07.v070_2_external_integrations_migration import (
    V0702ExternalIntegrationsMigration,
)

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
    V0402(),
    V0403(),
    V0404RealEstate(),
    V0405FlowsIcon(),
    V0406ContribTargetName(),
    V0407RECFProfitability(),
    V0408FundPortfolioAccount(),
    V0500ING(),
    V0501ExternalEntityProvider(),
    V0502(),
    V0503FundPortfolioTxs(),
    V0504(),
    V0505(),
    V0600Source(),
    V0601RecreatePositionTables(),
    V0602Source(),
    V0603FundETFFields(),
    V0604ManualPositionData(),
    V0605TxProductSubtype(),
    V0606(),
    V0700ContribTargetSubtype(),
    V0701CryptoCurrenciesV2(),
    V0702ExternalIntegrationsMigration(),
]
