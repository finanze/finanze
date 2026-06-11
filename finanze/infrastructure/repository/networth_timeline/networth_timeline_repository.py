import json
from datetime import date, datetime
from typing import Optional

from application.ports.networth_timeline_port import NetworthTimelinePort
from domain.dezimal import Dezimal
from domain.global_position import ProductType
from domain.networth_timeline import (
    HoldingValuation,
    MortgageValuation,
    NetworthTimelinePoint,
    NetworthTimelineState,
    PositionSnapshot,
)
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.networth_timeline.queries import NetworthTimelineQueries


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    return datetime.fromisoformat(value).date()


def _round2(value: Dezimal) -> str:
    return str(round(value, 2))


class NetworthTimelineSQLRepository(NetworthTimelinePort):
    def __init__(self, client: DBClient):
        self._db_client = client

    async def get_points(
        self, from_date: Optional[date], to_date: Optional[date]
    ) -> list[NetworthTimelinePoint]:
        sql = NetworthTimelineQueries.GET_POINTS_BASE.value
        conditions = []
        params = []
        if from_date is not None:
            conditions.append("date >= ?")
            params.append(from_date.isoformat())
        if to_date is not None:
            conditions.append("date <= ?")
            params.append(to_date.isoformat())
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY date ASC"

        async with self._db_client.read() as cursor:
            await cursor.execute(sql, tuple(params))
            rows = await cursor.fetchall()
            points = []
            for row in rows:
                breakdown_raw = json.loads(row["breakdown"]) if row["breakdown"] else {}
                breakdown = {k: Dezimal(v) for k, v in breakdown_raw.items()}
                points.append(
                    NetworthTimelinePoint(
                        date=date.fromisoformat(row["date"]),
                        total=Dezimal(row["total"]),
                        breakdown=breakdown,
                    )
                )
            return points

    async def get_state(self) -> NetworthTimelineState:
        async with self._db_client.read() as cursor:
            await cursor.execute(NetworthTimelineQueries.GET_STATE.value)
            row = await cursor.fetchone()
            if not row:
                return NetworthTimelineState()
            return NetworthTimelineState(
                inputs_signature=row["inputs_signature"],
                last_computed_date=_parse_date(row["last_computed_date"]),
            )

    async def persist(
        self,
        points: list[NetworthTimelinePoint],
        currency: str,
        state: NetworthTimelineState,
        wipe: bool,
    ):
        async with self._db_client.tx() as cursor:
            if wipe:
                await cursor.execute(NetworthTimelineQueries.DELETE_ALL_POINTS.value)
            for point in points:
                breakdown = {k: _round2(v) for k, v in point.breakdown.items()}
                await cursor.execute(
                    NetworthTimelineQueries.UPSERT_POINT.value,
                    (
                        point.date.isoformat(),
                        currency,
                        _round2(point.total),
                        json.dumps(breakdown),
                    ),
                )
            await cursor.execute(
                NetworthTimelineQueries.UPSERT_STATE.value,
                (
                    state.inputs_signature,
                    state.last_computed_date.isoformat()
                    if state.last_computed_date
                    else None,
                ),
            )

    async def get_position_snapshots(
        self, excluded_entity_ids: list[str]
    ) -> list[PositionSnapshot]:
        real_snapshots = await self._load_real_snapshots(excluded_entity_ids)
        import_rows = await self._load_batched_import_rows(excluded_entity_ids)

        gp_ids = set(real_snapshots.keys())
        gp_ids.update(row["gp_id"] for row in import_rows)
        if not gp_ids:
            return []

        holdings_by_gp = await self._load_holdings()

        for gp_id, snapshot in real_snapshots.items():
            snapshot.holdings = holdings_by_gp.get(gp_id, [])

        batched_snapshots = self._build_batched_snapshots(import_rows, holdings_by_gp)
        return list(real_snapshots.values()) + batched_snapshots

    async def _load_real_snapshots(
        self, excluded_entity_ids: list[str]
    ) -> dict[str, PositionSnapshot]:
        sql = NetworthTimelineQueries.GET_SNAPSHOTS_BASE.value
        params = []
        if excluded_entity_ids:
            placeholders = ", ".join("?" for _ in excluded_entity_ids)
            sql += f" AND gp.entity_id NOT IN ({placeholders})"
            params.extend(excluded_entity_ids)
        sql += " ORDER BY gp.date ASC"

        snapshots: dict[str, PositionSnapshot] = {}
        async with self._db_client.read() as cursor:
            await cursor.execute(sql, tuple(params))
            for row in await cursor.fetchall():
                holder = f"{row['entity_id']}|{row['ea_key']}|{row['source']}"
                snapshots[row["id"]] = PositionSnapshot(
                    holder=holder,
                    moment=datetime.fromisoformat(row["date"]),
                    holdings=[],
                    holder_deleted_at=_parse_date(row["deleted_at"]),
                )
        return snapshots

    async def _load_batched_import_rows(self, excluded_entity_ids: list[str]) -> list:
        sql = NetworthTimelineQueries.GET_BATCHED_IMPORTS.value
        params = []
        if excluded_entity_ids:
            placeholders = ", ".join("?" for _ in excluded_entity_ids)
            sql += f" AND gp.entity_id NOT IN ({placeholders})"
            params.extend(excluded_entity_ids)

        async with self._db_client.read() as cursor:
            await cursor.execute(sql, tuple(params))
            return await cursor.fetchall()

    def _build_batched_snapshots(
        self, import_rows: list, holdings_by_gp: dict[str, list[HoldingValuation]]
    ) -> list[PositionSnapshot]:
        # Each import of a re-declaring source (manual/sheets) carries the whole
        # portfolio for that source: collapse all of its positions into a single
        # snapshot held by the source, so the latest import on or before a day
        # fully replaces the previous one.
        imports: dict[str, dict] = {}
        for row in import_rows:
            entry = imports.get(row["import_id"])
            if entry is None:
                entry = {
                    "source": row["source"],
                    "date": row["import_date"],
                    "gp_ids": [],
                }
                imports[row["import_id"]] = entry
            entry["gp_ids"].append(row["gp_id"])

        snapshots: list[PositionSnapshot] = []
        for entry in imports.values():
            holdings: list[HoldingValuation] = []
            for gp_id in entry["gp_ids"]:
                holdings.extend(holdings_by_gp.get(gp_id, []))
            snapshots.append(
                PositionSnapshot(
                    holder=entry["source"],
                    moment=datetime.fromisoformat(entry["date"]),
                    holdings=holdings,
                    redeclaring=True,
                )
            )
        return snapshots

    async def _load_holdings(self) -> dict[str, list[HoldingValuation]]:
        holdings_by_gp: dict[str, list[HoldingValuation]] = {}
        async with self._db_client.read() as cursor:
            await cursor.execute(NetworthTimelineQueries.GET_HOLDING_VALUATIONS.value)
            for row in await cursor.fetchall():
                amount = row["amount"]
                if amount is None:
                    continue
                holdings_by_gp.setdefault(row["global_position_id"], []).append(
                    HoldingValuation(
                        product_type=ProductType(row["product_type"]),
                        currency=row["currency"],
                        amount=Dezimal(amount),
                        loan_ref=row["loan_ref"],
                    )
                )
        return holdings_by_gp

    async def get_mortgage_valuations(
        self, loan_refs: list[str]
    ) -> list[MortgageValuation]:
        if not loan_refs:
            return []
        placeholders = ", ".join("?" for _ in loan_refs)
        sql = NetworthTimelineQueries.GET_MORTGAGE_VALUATIONS.value.format(
            placeholders=placeholders
        )
        async with self._db_client.read() as cursor:
            await cursor.execute(sql, tuple(loan_refs))
            rows = await cursor.fetchall()
            return [
                MortgageValuation(
                    loan_ref=row["loan_ref"],
                    moment=datetime.fromisoformat(row["date"]),
                    outstanding=Dezimal(row["outstanding"]),
                    currency=row["currency"],
                    origination=_parse_date(row["origination"]),
                )
                for row in rows
            ]
