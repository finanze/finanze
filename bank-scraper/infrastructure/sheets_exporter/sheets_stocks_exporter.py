import datetime

from domain.bank import Bank

STOCKS_SHEET = "Stocks"


def update_stocks(sheet, summary: dict, sheet_id: str):
    stock_rows = map_stocks(summary)

    request = sheet.values().update(
        spreadsheetId=sheet_id,
        range=f"{STOCKS_SHEET}!A1",
        valueInputOption="RAW",
        body={"values": stock_rows},
    )

    request.execute()


def map_stocks(summary):
    return [
        [None, datetime.datetime.now(datetime.timezone.utc).isoformat()],
        [],
        *map_myi_stocks(summary),
        *map_tr_stocks(summary),
        *[["" for _ in range(20)] for _ in range(20)],
    ]


def map_myi_stocks(summary):
    try:
        details = summary.get(Bank.MY_INVESTOR.name, None).investments.stocks.details
    except AttributeError:
        return []

    return [
        [
            stock.name,
            stock.isin,
            stock.ticker,
            stock.market,
            stock.shares,
            stock.initialInvestment,
            stock.averageBuyPrice,
            stock.marketValue,
            stock.currency,
            stock.type,
            stock.subtype,
            "MYI",
        ]
        for stock in details
    ]


def map_tr_stocks(summary):
    try:
        details = summary.get(Bank.TRADE_REPUBLIC.name, None).investments.stocks.details
    except AttributeError:
        return []

    return [
        [
            stock.name,
            stock.isin,
            stock.ticker,
            stock.market,
            stock.shares,
            stock.initialInvestment,
            stock.averageBuyPrice,
            stock.marketValue,
            stock.currency,
            stock.type,
            stock.subtype,
            "TR",
        ]
        for stock in details
    ]
