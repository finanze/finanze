import datetime

from dateutil.tz import tzlocal

from domain.financial_entity import Entity

STOCKS_SHEET = "Stocks"


def update_stocks(sheet, global_position: dict, sheet_id: str):
    stock_rows = map_stocks(global_position)

    request = sheet.values().update(
        spreadsheetId=sheet_id,
        range=f"{STOCKS_SHEET}!A1",
        valueInputOption="RAW",
        body={"values": stock_rows},
    )

    request.execute()


def map_stocks(global_position):
    return [
        [None, datetime.datetime.now(tzlocal()).isoformat()],
        [],
        *map_myi_stocks(global_position),
        *map_tr_stocks(global_position),
        *[["" for _ in range(20)] for _ in range(20)],
    ]


def map_myi_stocks(global_position):
    try:
        details = global_position.get(Entity.MY_INVESTOR.name, None).investments.stocks.details
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


def map_tr_stocks(global_position):
    try:
        details = global_position.get(Entity.TRADE_REPUBLIC.name, None).investments.stocks.details
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
