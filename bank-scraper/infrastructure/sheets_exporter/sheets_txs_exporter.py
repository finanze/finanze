import datetime

from domain.transactions import Transactions

TXS_SHEET = "TXs"


def update_transactions(sheet, txs: Transactions, sheet_id: str):
    tx_rows = map_investment_txs(txs.investment)

    request = sheet.values().update(
        spreadsheetId=sheet_id,
        range=f"{TXS_SHEET}!A1",
        valueInputOption="RAW",
        body={"values": tx_rows},
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
        tx.orderDate.isoformat(),
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
