import datetime

from domain.bank import Bank

CONTRIBUTIONS_SHEET = "Auto Contribuciones"


def update_contributions(sheet, contributions: dict, sheet_id: str):
    contributions_rows = map_periodic_contributions(contributions)

    request = sheet.values().update(
        spreadsheetId=sheet_id,
        range=f"{CONTRIBUTIONS_SHEET}!A1",
        valueInputOption="RAW",
        body={"values": contributions_rows},
    )

    request.execute()


def map_periodic_contributions(contributions):
    try:
        contributions = contributions.get(Bank.MY_INVESTOR.name, None).periodic
    except AttributeError:
        return []

    return [
        [None, datetime.datetime.now(datetime.timezone.utc).isoformat()],
        [],
        *[
            [
                contrib.alias,
                contrib.isin,
                contrib.amount,
                contrib.since.isoformat()[:10],
                contrib.until.isoformat()[:10] if contrib.until else None,
                contrib.frequency,
                contrib.active,
                "MYI",
            ]
            for contrib in contributions
        ],
        *[["" for _ in range(20)] for _ in range(20)],
    ]
