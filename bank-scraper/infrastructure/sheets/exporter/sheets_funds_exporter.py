import datetime

from dateutil.tz import tzlocal

from domain.financial_entity import Entity

FUNDS_SHEET = "Funds"


def update_funds(sheet, global_position: dict, sheet_id: str):
    fund_rows = map_funds(global_position)

    request = sheet.values().update(
        spreadsheetId=sheet_id,
        range=f"{FUNDS_SHEET}!A1",
        valueInputOption="RAW",
        body={"values": fund_rows},
    )

    request.execute()


def map_funds(global_position):
    try:
        details = global_position.get(Entity.MY_INVESTOR.name, None).investments.funds.details
    except AttributeError:
        return []

    return [
        [None, datetime.datetime.now(tzlocal()).isoformat()],
        [],
        *[
            [
                fund.name,
                fund.isin,
                fund.market,
                fund.shares,
                fund.initialInvestment,
                fund.averageBuyPrice,
                fund.marketValue,
                fund.currency,
                "MYI",
            ]
            for fund in details
        ],
        *[["" for _ in range(20)] for _ in range(20)],
    ]
