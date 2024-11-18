import datetime

from domain.bank import Bank

OTHER_SHEET = "Other"


def update_other(sheet, summary: dict, sheet_id: str):
    stock_rows = map_stocks(summary)

    request = sheet.values().update(
        spreadsheetId=sheet_id,
        range=f"{OTHER_SHEET}!A1",
        valueInputOption="RAW",
        body={"values": stock_rows},
    )

    request.execute()


def map_stocks(summary):
    return [
        [None, datetime.datetime.now(datetime.timezone.utc).isoformat()],
        [],
        *map_myi_sego_investments(summary),
        *[["" for _ in range(20)] for _ in range(20)],
    ]


def map_myi_sego_investments(summary):
    try:
        details = summary.get(Bank.MY_INVESTOR.name, None).investments.sego.details
    except AttributeError:
        return []

    return [
        [
            i.name,
            "",
            "",
            "",
            1,
            i.amount,
            i.amount,
            i.amount,
            "EUR",
            "SEGO",
            i.type,
            i.interestRate,
            i.maturity,
            "MYI",
        ]
        for i in details
    ]
