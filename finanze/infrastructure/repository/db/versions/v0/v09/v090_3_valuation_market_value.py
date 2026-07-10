import json

from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.upgrader import DBVersionMigration


class V0903ValuationMarketValue(DBVersionMigration):
    @property
    def name(self):
        return "v0.9.0:3_valuation_market_value"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        await cursor.execute(
            "SELECT id, purchase_date, estimated_market_value, valuations FROM real_estate"
        )
        rows = list(cursor)

        for row in rows:
            re_id = row["id"]
            purchase_date = row["purchase_date"]
            estimated_market_value = row["estimated_market_value"]
            raw_valuations = row["valuations"]

            valuations = json.loads(raw_valuations) if raw_valuations else []

            changed = False
            for valuation in valuations:
                if "market_value" not in valuation:
                    valuation["market_value"] = False
                    changed = True

            if not any(valuation.get("market_value") for valuation in valuations):
                purchase_date_iso = (
                    purchase_date
                    if isinstance(purchase_date, str)
                    else purchase_date.isoformat()
                )
                valuations.append(
                    {
                        "date": purchase_date_iso,
                        "amount": str(estimated_market_value),
                        "notes": None,
                        "market_value": True,
                    }
                )
                changed = True

            if changed:
                await cursor.execute(
                    "UPDATE real_estate SET valuations = ? WHERE id = ?",
                    (json.dumps(valuations), re_id),
                )
