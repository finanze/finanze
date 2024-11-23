import datetime

from domain.auto_contributions import AutoContributions, PeriodicContribution

CONTRIBUTIONS_SHEET = "Auto Contribuciones"


def update_contributions(sheet, contributions: dict[str, AutoContributions], sheet_id: str):
    periodic = []
    for contrib in contributions.values():
        periodic.extend(contrib.periodic)
    periodic = sorted(periodic, key=lambda c: (c.isin, c.since))
    periodic_contributions_rows = map_periodic_contributions(periodic)

    request = sheet.values().update(
        spreadsheetId=sheet_id,
        range=f"{CONTRIBUTIONS_SHEET}!A1",
        valueInputOption="RAW",
        body={"values": periodic_contributions_rows},
    )

    request.execute()


def map_periodic_contributions(contributions: list[PeriodicContribution]):
    if not contributions:
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
