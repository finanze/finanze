from dataclasses import dataclass

from domain.use_cases.add_manual_transaction import AddManualTransaction
from domain.use_cases.calculate_loan import CalculateLoan
from domain.use_cases.calculate_savings import CalculateSavings
from domain.use_cases.connect_crypto_wallet import ConnectCryptoWallet
from domain.use_cases.connect_external_integration import ConnectExternalIntegration
from domain.use_cases.create_label import CreateLabel
from domain.use_cases.create_labeling_rule import CreateLabelingRule
from domain.use_cases.create_real_estate import CreateRealEstate
from domain.use_cases.delete_crypto_wallet import DeleteCryptoWalletConnection
from domain.use_cases.delete_label import DeleteLabel
from domain.use_cases.delete_labeling_rule import DeleteLabelingRule
from domain.use_cases.delete_manual_historic_entry import DeleteManualHistoricEntry
from domain.use_cases.delete_manual_transaction import DeleteManualTransaction
from domain.use_cases.delete_pending_flow import DeletePendingFlow
from domain.use_cases.delete_periodic_flow import DeletePeriodicFlow
from domain.use_cases.delete_real_estate import DeleteRealEstate
from domain.use_cases.derive_crypto_addresses import DeriveCryptoAddresses
from domain.use_cases.disconnect_external_integration import (
    DisconnectExternalIntegration,
)
from domain.use_cases.fetch_crypto_data import FetchCryptoData
from domain.use_cases.fetch_financial_data import FetchFinancialData
from domain.use_cases.forecast import Forecast
from domain.use_cases.get_available_entities import GetAvailableEntities
from domain.use_cases.get_cashflow_summary import GetCashflowSummary
from domain.use_cases.get_contributions import GetContributions
from domain.use_cases.get_crypto_asset_details import GetCryptoAssetDetails
from domain.use_cases.get_crypto_wallet_addresses import GetCryptoWalletAddresses
from domain.use_cases.get_euribor_rates import GetEuriborRates
from domain.use_cases.get_exchange_rates import GetExchangeRates
from domain.use_cases.get_external_integrations import GetExternalIntegrations
from domain.use_cases.get_gains_timeline import GetGainsTimeline
from domain.use_cases.get_historic import GetHistoric
from domain.use_cases.get_instrument_info import GetInstrumentInfo
from domain.use_cases.get_instruments import GetInstruments
from domain.use_cases.get_labeling_rules import GetLabelingRules
from domain.use_cases.get_labels import GetLabels
from domain.use_cases.get_money_events import GetMoneyEvents
from domain.use_cases.get_networth_summary import GetNetworthSummary
from domain.use_cases.get_networth_timeline import GetNetworthTimeline
from domain.use_cases.get_periodic_flows import GetPeriodicFlows
from domain.use_cases.get_position import GetPosition
from domain.use_cases.get_recurring_movements import GetRecurringMovements
from domain.use_cases.get_settings import GetSettings
from domain.use_cases.get_transactions import GetTransactions
from domain.use_cases.ignore_recurring_movement import IgnoreRecurringMovement
from domain.use_cases.list_real_estate import ListRealEstate
from domain.use_cases.partial_amortize_manual_investment import (
    PartialAmortizeManualInvestment,
)
from domain.use_cases.preview_labeling_rule import PreviewLabelingRule
from domain.use_cases.query_pending_flows import QueryPendingFlows
from domain.use_cases.relabel_transactions import RelabelTransactions
from domain.use_cases.restore_recurring_movement import RestoreRecurringMovement
from domain.use_cases.save_commodities import SaveCommodities
from domain.use_cases.save_pending_flow import SavePendingFlow
from domain.use_cases.save_periodic_flow import SavePeriodicFlow
from domain.use_cases.search_crypto_assets import SearchCryptoAssets
from domain.use_cases.settle_manual_investment import SettleManualInvestment
from domain.use_cases.settle_pending_flow import SettlePendingFlow
from domain.use_cases.unsettle_manual_investment import UnsettleManualInvestment
from domain.use_cases.update_contributions import UpdateContributions
from domain.use_cases.update_crypto_wallet import UpdateCryptoWalletConnection
from domain.use_cases.update_label import UpdateLabel
from domain.use_cases.update_labeling_rule import UpdateLabelingRule
from domain.use_cases.update_manual_transaction import UpdateManualTransaction
from domain.use_cases.update_pending_flow import UpdatePendingFlow
from domain.use_cases.update_periodic_flow import UpdatePeriodicFlow
from domain.use_cases.update_position import UpdatePosition
from domain.use_cases.update_real_estate import UpdateRealEstate
from domain.use_cases.update_transaction_labels import UpdateTransactionLabels


@dataclass
class McpUseCases:
    get_settings: GetSettings
    get_available_entities: GetAvailableEntities
    get_networth_summary: GetNetworthSummary
    get_position: GetPosition
    update_position: UpdatePosition
    get_contributions: GetContributions
    update_contributions: UpdateContributions
    get_historic: GetHistoric
    settle_manual_investment: SettleManualInvestment
    partial_amortize_manual_investment: PartialAmortizeManualInvestment
    unsettle_manual_investment: UnsettleManualInvestment
    delete_manual_historic_entry: DeleteManualHistoricEntry
    get_networth_timeline: GetNetworthTimeline
    get_gains_timeline: GetGainsTimeline
    get_transactions: GetTransactions
    add_manual_transaction: AddManualTransaction
    update_manual_transaction: UpdateManualTransaction
    delete_manual_transaction: DeleteManualTransaction
    update_transaction_labels: UpdateTransactionLabels
    get_periodic_flows: GetPeriodicFlows
    save_periodic_flow: SavePeriodicFlow
    update_periodic_flow: UpdatePeriodicFlow
    delete_periodic_flow: DeletePeriodicFlow
    query_pending_flows: QueryPendingFlows
    save_pending_flow: SavePendingFlow
    update_pending_flow: UpdatePendingFlow
    delete_pending_flow: DeletePendingFlow
    settle_pending_flow: SettlePendingFlow
    get_money_events: GetMoneyEvents
    get_labels: GetLabels
    create_label: CreateLabel
    update_label: UpdateLabel
    delete_label: DeleteLabel
    get_labeling_rules: GetLabelingRules
    create_labeling_rule: CreateLabelingRule
    update_labeling_rule: UpdateLabelingRule
    delete_labeling_rule: DeleteLabelingRule
    preview_labeling_rule: PreviewLabelingRule
    relabel_transactions: RelabelTransactions
    get_cashflow_summary: GetCashflowSummary
    get_recurring_movements: GetRecurringMovements
    ignore_recurring_movement: IgnoreRecurringMovement
    restore_recurring_movement: RestoreRecurringMovement
    get_exchange_rates: GetExchangeRates
    get_euribor_rates: GetEuriborRates
    get_instruments: GetInstruments
    get_instrument_info: GetInstrumentInfo
    search_crypto_assets: SearchCryptoAssets
    get_crypto_asset_details: GetCryptoAssetDetails
    get_crypto_wallet_addresses: GetCryptoWalletAddresses
    derive_crypto_addresses: DeriveCryptoAddresses
    connect_crypto_wallet: ConnectCryptoWallet
    update_crypto_wallet: UpdateCryptoWalletConnection
    delete_crypto_wallet: DeleteCryptoWalletConnection
    fetch_crypto_data: FetchCryptoData
    save_commodities: SaveCommodities
    get_external_integrations: GetExternalIntegrations
    connect_external_integration: ConnectExternalIntegration
    disconnect_external_integration: DisconnectExternalIntegration
    list_real_estate: ListRealEstate
    create_real_estate: CreateRealEstate
    update_real_estate: UpdateRealEstate
    delete_real_estate: DeleteRealEstate
    calculate_savings: CalculateSavings
    calculate_loan: CalculateLoan
    forecast: Forecast
    fetch_financial_data: FetchFinancialData
