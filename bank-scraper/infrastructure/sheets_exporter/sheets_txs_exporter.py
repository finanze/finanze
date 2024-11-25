import datetime

from domain.transactions import Transactions
from infrastructure.sheets_exporter.sheets_contribs_exporter import map_last_update_row

TXS_SHEET = "TXs"


def update_transactions(sheet, txs: Transactions, sheet_id: str, last_update: dict[str, datetime]):
    tx_rows = map_investment_txs(txs.investment)

    last_update_row = map_last_update_row(last_update)
    rows = [last_update_row, *tx_rows]

    request = sheet.values().update(
        spreadsheetId=sheet_id,
        range=f"{TXS_SHEET}!A1",
        valueInputOption="RAW",
        body={"values": rows},
    )

    request.execute()


def map_base_tx(tx):
    return [
        tx.id,
        tx.name,
        tx.amount,
        tx.currency,
        tx.currencySymbol,
        tx.type,
        tx.date.isoformat(),
        tx.source,
    ]


def map_investment_tx(tx):
    stock = tx.productType == "STOCK_ETF"
    return [
        *map_base_tx(tx),
        "",
        tx.productType,
        tx.netAmount,
        tx.isin,
        tx.ticker if stock else "",
        tx.shares,
        tx.price,
        tx.market,
        tx.fees,
        tx.orderDate.isoformat() if tx.orderDate else "",
    ]


def map_investment_txs(txs):
    if not txs:
        return []

    return [
        [None, datetime.datetime.now(datetime.timezone.utc).isoformat()],
        [],
        *[
            map_investment_tx(tx) for tx in txs
        ],
        *[["" for _ in range(20)] for _ in range(20)],
    ]
