import datetime

from dateutil.tz import tzlocal

from domain.bank import Bank

OTHER_SHEET = "Other"


def update_other(sheet, global_position: dict, sheet_id: str):
    stock_rows = map_investments(global_position)

    request = sheet.values().update(
        spreadsheetId=sheet_id,
        range=f"{OTHER_SHEET}!A1",
        valueInputOption="RAW",
        body={"values": stock_rows},
    )

    request.execute()


def map_investments(global_position):
    return [
        [None, datetime.datetime.now(tzlocal()).isoformat()],
        [],
        *map_factoring_investments(global_position),
        *[["" for _ in range(20)] for _ in range(20)],
    ]


def map_factoring_investments(global_position):
    try:
        details = global_position.get(Bank.SEGO.name, None).investments.factoring.details
    except AttributeError:
        return []

    return [
        [
            i.name,
            i.amount,
            "EUR",
            "FACTORING",
            i.type,
            i.interestRate,
            i.netInterestRate,
            i.lastInvestDate.isoformat(),
            i.maturity.isoformat()[:10],
            i.state,
            "SEGO",
        ]
        for i in details
    ]
