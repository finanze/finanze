import datetime

from domain.auto_contributions import AutoContributions, PeriodicContribution

CONTRIBUTIONS_SHEET = "Auto Contribuciones"


def update_contributions(sheet,
                         contributions: dict[str, AutoContributions],
                         sheet_id: str,
                         last_update: dict[str, datetime]):
    periodic = []
    for contrib in contributions.values():
        periodic.extend(contrib.periodic)
    periodic = sorted(periodic, key=lambda c: (c.isin, c.since))

    last_update = sorted(last_update.items(), key=lambda item: item[1], reverse=False)
    last_update_row = [None]
    for k, v in last_update:
        last_update_row.append(k)
        last_update_row.append(v.isoformat())
    last_update_row.extend(["" for _ in range(10)])
    periodic_contributions_rows = map_periodic_contributions(periodic)

    rows = [last_update_row, *periodic_contributions_rows]

    request = sheet.values().update(
        spreadsheetId=sheet_id,
        range=f"{CONTRIBUTIONS_SHEET}!A1",
        valueInputOption="RAW",
        body={"values": rows},
    )

    request.execute()


def map_periodic_contributions(contributions: list[PeriodicContribution]):
    if not contributions:
        return []

    return [
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
