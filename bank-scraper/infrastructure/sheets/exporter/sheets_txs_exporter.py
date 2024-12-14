import datetime
from typing import Union

from domain.transactions import Transactions, BaseTx, BaseInvestmentTx, FundTx, StockTx, FactoringTx, RealStateCFTx, \
    AccountTx
from infrastructure.sheets.exporter.sheets_contribs_exporter import map_last_update_row

INVESTMENT_TXS_SHEET = "Investment TXs"
ACCOUNT_TXS_SHEET = "Account TXs"


def update_transactions(sheet, txs: Transactions, sheet_id: str, last_update: dict[str, datetime]):
    inv_tx_rows = map_investment_txs(txs.investment)

    inv_last_update_row = map_last_update_row(last_update)
    inv_rows = [inv_last_update_row, [], *inv_tx_rows]

    request = sheet.values().update(
        spreadsheetId=sheet_id,
        range=f"{INVESTMENT_TXS_SHEET}!A1",
        valueInputOption="RAW",
        body={"values": inv_rows},
    )

    request.execute()

    acc_tx_rows = map_account_txs(txs.account)

    acc_last_update_row = map_last_update_row(last_update)
    acc_rows = [acc_last_update_row, [], *acc_tx_rows]

    request = sheet.values().update(
        spreadsheetId=sheet_id,
        range=f"{ACCOUNT_TXS_SHEET}!A1",
        valueInputOption="RAW",
        body={"values": acc_rows},
    )

    request.execute()


def map_base_tx(tx: BaseTx):
    return [
        tx.id,
        tx.name,
        tx.amount,
        tx.currency,
        tx.currencySymbol,
        tx.type,
        tx.date.isoformat(),
        tx.entity,
    ]


def map_investment_tx(tx: BaseInvestmentTx):
    map_fn = map_fund_stock_investment_tx
    if isinstance(tx, FactoringTx):
        map_fn = map_factoring_tx
    elif isinstance(tx, RealStateCFTx):
        map_fn = map_real_state_cf_tx

    return [
        *map_base_tx(tx),
        "",
        tx.productType,
        *map_fn(tx),
        *["" for _ in range(10)],
    ]


def map_account_tx(tx: AccountTx):
    return [
        *map_base_tx(tx),
        tx.fees,
        tx.retentions,
        tx.interestRate,
        tx.avgBalance
    ]


def map_fund_stock_investment_tx(tx: Union[FundTx, StockTx]):
    stock = tx.productType == "STOCK_ETF"
    return [
        tx.netAmount,
        tx.isin,
        tx.ticker if stock else "",
        tx.shares,
        tx.price,
        tx.market,
        tx.fees,
        tx.orderDate.isoformat() if tx.orderDate else "",
    ]


def map_factoring_tx(tx: FactoringTx):
    return [
        tx.netAmount or "",
        "",
        "",
        "",
        "",
        "",
        tx.fees or "",
        "",
        tx.retentions or "",
        tx.interests or ""
    ]


def map_real_state_cf_tx(tx: RealStateCFTx):
    return [
        tx.netAmount or "",
        "",
        "",
        "",
        "",
        "",
        tx.fees or "",
        "",
        tx.retentions or "",
        tx.interests or ""
    ]


def map_investment_txs(txs):
    if not txs:
        return []

    return [
        *[
            map_investment_tx(tx) for tx in txs
        ],
        *[["" for _ in range(20)] for _ in range(20)],
    ]


def map_account_txs(txs):
    if not txs:
        return []

    return [
        *[
            map_account_tx(tx) for tx in txs
        ],
        *[["" for _ in range(20)] for _ in range(20)],
    ]
