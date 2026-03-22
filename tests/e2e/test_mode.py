import domain.native_entities as native_entities
from e2e.mock_fetcher import (
    MockCryptoExchangeFetcher,
    MockFinancialEntityFetcher,
    MockPinEntityFetcher,
)


def get_e2e_financial_fetchers() -> dict:
    simple = [
        native_entities.MY_INVESTOR,
        native_entities.UNICAJA,
        native_entities.URBANITAE,
        native_entities.WECITY,
        native_entities.SEGO,
        native_entities.MINTOS,
        native_entities.F24,
        native_entities.INDEXA_CAPITAL,
        native_entities.ING,
        native_entities.CAJAMAR,
        native_entities.DEGIRO,
        native_entities.IBKR,
    ]

    fetchers = {entity: MockFinancialEntityFetcher(entity) for entity in simple}
    fetchers[native_entities.TRADE_REPUBLIC] = MockPinEntityFetcher(
        native_entities.TRADE_REPUBLIC
    )
    fetchers[native_entities.BINANCE] = MockCryptoExchangeFetcher(
        native_entities.BINANCE
    )
    return fetchers
