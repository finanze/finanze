from collections import defaultdict
from dataclasses import replace
from datetime import date, datetime
from typing import Optional
from uuid import UUID

from application.ports.gains_timeline_port import GainsTimelinePort
from dateutil.tz import tzlocal
from domain.commodity import CommodityType, WeightUnit, to_troy_ounces
from domain.dezimal import Dezimal
from domain.gains_timeline import (
    AssetSnapshot,
    AssetValuation,
    GainsAssetFilter,
    GainsFlow,
    GainsSettlement,
)
from domain.global_position import EquityType, ProductType
from domain.transactions import TxType
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.gains_timeline.queries import GainsTimelineQueries


_AGGREGATED_MARKET_TYPES = {
    ProductType.STOCK_ETF,
    ProductType.FUND,
    ProductType.CRYPTO,
}


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    return _parse_datetime(value).date()


def _parse_datetime(value: str) -> datetime:
    moment = datetime.fromisoformat(value)
    if moment.tzinfo is None:
        return moment.replace(tzinfo=tzlocal())
    return moment.astimezone(tzlocal())


def _holder(entity_id: str, entity_account_id: str, source: str) -> str:
    if source in ("MANUAL", "SHEETS"):
        return source
    return f"{entity_id}|{entity_account_id}|{source}"


class GainsTimelineSQLRepository(GainsTimelinePort):
    def __init__(self, client: DBClient):
        self._db_client = client

    async def get_asset_snapshots(
        self,
        assets: list[GainsAssetFilter],
        entity_ids: list[str],
        from_date: Optional[date] = None,
    ) -> list[AssetSnapshot]:
        if not entity_ids:
            return []
        real_snapshots = await self._load_real_snapshots(entity_ids, from_date)
        import_rows = await self._load_batched_import_rows(entity_ids)
        position_ids = set(real_snapshots)
        position_ids.update(
            row["gp_id"] for row in import_rows if row["gp_id"] is not None
        )
        if not position_ids:
            return []

        valuations = await self._load_valuations(position_ids, assets)
        for position_id, snapshot in real_snapshots.items():
            snapshot.valuations = valuations.get(position_id, [])
        snapshots = list(real_snapshots.values()) + self._build_batched_snapshots(
            import_rows, valuations
        )
        for snapshot in snapshots:
            snapshot.valuations = self._merge_market_asset_valuations(
                snapshot.valuations
            )
        return snapshots

    async def get_flows(
        self, assets: list[GainsAssetFilter], entity_ids: list[str]
    ) -> list[GainsFlow]:
        product_types = self._product_types(assets)
        selected_crypto_wallet_ids = self._selected_crypto_wallet_ids(assets)
        if not product_types or not entity_ids:
            return []
        product_placeholders = ", ".join("?" for _ in product_types)
        entity_placeholders = ", ".join("?" for _ in entity_ids)
        sql = (
            GainsTimelineQueries.GET_FLOWS_BASE.value
            + f" WHERE it.product_type IN ({product_placeholders})"
            + f" AND it.entity_id IN ({entity_placeholders})"
            + " ORDER BY it.date ASC"
        )
        params = [*product_types, *entity_ids]
        async with self._db_client.read() as cursor:
            await cursor.execute(sql, tuple(params))
            rows = await cursor.fetchall()
        flows = [
            GainsFlow(
                holder=_holder(row["entity_id"], row["ea_key"], row["source"]),
                product_type=ProductType(row["product_type"]),
                asset_key=row["asset_key"],
                moment=_parse_datetime(row["date"]),
                amount=Dezimal(row["amount"]),
                currency=row["currency"],
                portfolio_name=row["portfolio_name"] or None,
                equity_type=EquityType(row["equity_type"])
                if row["equity_type"]
                else None,
                quantity=Dezimal(row["quantity"])
                if row["quantity"] is not None
                else None,
                net_amount=Dezimal(row["net_amount"])
                if row["net_amount"] is not None
                else None,
                fees=Dezimal(row["fees"]),
                retentions=Dezimal(row["retentions"]),
                transaction_type=TxType(row["type"]),
                name=row["asset_name"] or None,
            )
            for row in rows
            if row["asset_key"]
            and not (
                selected_crypto_wallet_ids is not None
                and row["product_type"] == ProductType.CRYPTO.value
            )
        ]
        return self._deduplicate_factoring_flows(flows)

    async def get_settlements(
        self, assets: list[GainsAssetFilter], entity_ids: list[str]
    ) -> list[GainsSettlement]:
        product_types = sorted(
            {
                asset.product_type.value
                for asset in assets
                if asset.product_type
                in {ProductType.FACTORING, ProductType.REAL_ESTATE_CF}
            }
        )
        if not product_types or not entity_ids:
            return []
        product_placeholders = ", ".join("?" for _ in product_types)
        entity_placeholders = ", ".join("?" for _ in entity_ids)
        sql = (
            GainsTimelineQueries.GET_SETTLEMENTS_BASE.value
            + f" AND h.product_type IN ({product_placeholders})"
            + f" AND h.entity_id IN ({entity_placeholders})"
            + " ORDER BY date ASC"
        )
        params = [*product_types, *entity_ids]
        async with self._db_client.read() as cursor:
            await cursor.execute(sql, tuple(params))
            rows = await cursor.fetchall()
        return [
            GainsSettlement(
                holder=_holder(row["entity_id"], row["ea_key"], row["source"]),
                product_type=ProductType(row["product_type"]),
                asset_key=row["asset_key"],
                moment=_parse_datetime(row["date"]),
                net_proceeds=Dezimal(row["net_proceeds"]),
                currency=row["currency"],
            )
            for row in rows
            if row["asset_key"] and row["date"]
        ]

    async def get_data_version(self) -> str:
        async with self._db_client.read() as cursor:
            await cursor.execute(GainsTimelineQueries.GET_DATA_VERSION.value)
            row = await cursor.fetchone()
            return row["value"] if row else ""

    async def _load_real_snapshots(
        self, entity_ids: list[str], from_date: Optional[date] = None
    ) -> dict[str, AssetSnapshot]:
        placeholders = ", ".join("?" for _ in entity_ids)
        sql = (
            GainsTimelineQueries.GET_REAL_SNAPSHOTS_BASE.value
            + f" AND gp.entity_id IN ({placeholders})"
        )
        params: list = list(entity_ids)
        if from_date is not None:
            boundary = f"{from_date.isoformat()}T00:00:00"
            sql += (
                " AND (gp.date >= ? OR gp.date = ("
                "SELECT MAX(g2.date) FROM global_positions g2 "
                "WHERE g2.source = 'REAL' AND g2.entity_id = gp.entity_id "
                "AND COALESCE(g2.entity_account_id, '') = COALESCE(gp.entity_account_id, '') "
                "AND g2.date < ?))"
            )
            params.extend([boundary, boundary])
        sql += " ORDER BY gp.date ASC"
        async with self._db_client.read() as cursor:
            await cursor.execute(sql, tuple(params))
            rows = await cursor.fetchall()
        return {
            row["id"]: AssetSnapshot(
                holder=_holder(row["entity_id"], row["ea_key"], row["source"]),
                moment=_parse_datetime(row["date"]),
                holder_deleted_at=_parse_date(row["deleted_at"]),
            )
            for row in rows
        }

    async def _load_batched_import_rows(self, entity_ids: list[str]) -> list:
        placeholders = ", ".join("?" for _ in entity_ids)
        sql = (
            GainsTimelineQueries.GET_BATCHED_IMPORTS_BASE.value
            + f" AND (vdi.entity_id IS NULL OR vdi.entity_id IN ({placeholders}))"
        )
        async with self._db_client.read() as cursor:
            await cursor.execute(sql, tuple(entity_ids))
            return await cursor.fetchall()

    async def _load_valuations(
        self, position_ids: set[str], assets: list[GainsAssetFilter]
    ) -> dict[str, list[AssetValuation]]:
        product_types = self._product_types(assets)
        selected_crypto_wallet_ids = self._selected_crypto_wallet_ids(assets)
        position_placeholders = ", ".join("?" for _ in position_ids)
        product_placeholders = ", ".join("?" for _ in product_types)
        sql = (
            "SELECT * FROM ("
            + GainsTimelineQueries.GET_ASSET_VALUATIONS_BASE.value
            + f") WHERE global_position_id IN ({position_placeholders})"
            + f" AND product_type IN ({product_placeholders})"
        )
        params = [*position_ids, *product_types]
        valuations: dict[str, list[AssetValuation]] = defaultdict(list)
        async with self._db_client.read() as cursor:
            await cursor.execute(sql, tuple(params))
            rows = await cursor.fetchall()
        for row in rows:
            if row["market_value"] is None or not row["asset_key"]:
                continue
            product_type = ProductType(row["product_type"])
            wallet_id = (
                UUID(row["wallet_id"])
                if product_type == ProductType.CRYPTO
                and selected_crypto_wallet_ids is not None
                and row["wallet_id"]
                else None
            )
            if (
                product_type == ProductType.CRYPTO
                and selected_crypto_wallet_ids is not None
                and wallet_id not in selected_crypto_wallet_ids
            ):
                continue
            valuations[row["global_position_id"]].append(
                AssetValuation(
                    product_type=product_type,
                    asset_key=row["asset_key"],
                    currency=row["currency"],
                    market_value=Dezimal(row["market_value"]),
                    portfolio_name=row["portfolio_name"] or None,
                    equity_type=EquityType(row["equity_type"])
                    if row["equity_type"]
                    else None,
                    quantity=self._quantity(row),
                    cost_basis=Dezimal(row["cost_basis"])
                    if row["cost_basis"] is not None
                    else None,
                    interest_rate=Dezimal(row["interest_rate"])
                    if row["interest_rate"] is not None
                    else None,
                    start_date=_parse_date(row["start_date"]),
                    maturity=_parse_date(row["maturity"]),
                    extended_maturity=_parse_date(row["extended_maturity"]),
                    extended_interest_rate=Dezimal(row["extended_interest_rate"])
                    if row["extended_interest_rate"] is not None
                    else None,
                    late_interest_rate=Dezimal(row["late_interest_rate"])
                    if row["late_interest_rate"] is not None
                    else None,
                    commodity_type=CommodityType(row["commodity_type"])
                    if row["commodity_type"] is not None
                    else None,
                    weight=Dezimal(row["weight"])
                    if row["weight"] is not None
                    else None,
                    weight_unit=WeightUnit(row["weight_unit"])
                    if row["weight_unit"] is not None
                    else None,
                    wallet_id=wallet_id,
                )
            )
        return {
            position_id: self._merge_market_asset_valuations(position_valuations)
            for position_id, position_valuations in valuations.items()
        }

    @staticmethod
    def _merge_market_asset_valuations(
        valuations: list[AssetValuation],
    ) -> list[AssetValuation]:
        merged: dict[
            tuple[
                ProductType,
                str,
                str,
                Optional[str],
                Optional[EquityType],
                Optional[UUID],
            ],
            AssetValuation,
        ] = {}
        remaining: list[AssetValuation] = []
        for valuation in valuations:
            if valuation.product_type not in _AGGREGATED_MARKET_TYPES:
                remaining.append(valuation)
                continue
            key = (
                valuation.product_type,
                valuation.asset_key,
                valuation.currency,
                valuation.portfolio_name,
                valuation.equity_type,
                valuation.wallet_id,
            )
            previous = merged.get(key)
            if previous is None:
                merged[key] = valuation
                continue
            merged[key] = replace(
                previous,
                market_value=previous.market_value + valuation.market_value,
                quantity=GainsTimelineSQLRepository._sum_optional(
                    previous.quantity, valuation.quantity
                ),
                cost_basis=GainsTimelineSQLRepository._sum_optional(
                    previous.cost_basis, valuation.cost_basis
                ),
            )
        return [*remaining, *merged.values()]

    @staticmethod
    def _sum_optional(
        previous: Optional[Dezimal], current: Optional[Dezimal]
    ) -> Optional[Dezimal]:
        if previous is None:
            return current
        if current is None:
            return previous
        return previous + current

    @staticmethod
    def _quantity(row) -> Optional[Dezimal]:
        if row["quantity"] is None:
            return None
        quantity = Dezimal(row["quantity"])
        if row["product_type"] != ProductType.COMMODITY.value:
            return quantity
        return to_troy_ounces(quantity, WeightUnit(row["quantity_unit"]))

    @staticmethod
    def _build_batched_snapshots(
        import_rows: list, valuations: dict[str, list[AssetValuation]]
    ) -> list[AssetSnapshot]:
        imports: dict[str, dict] = {}
        for row in import_rows:
            entry = imports.get(row["import_id"])
            if entry is None:
                entry = {
                    "source": row["source"],
                    "date": row["import_date"],
                    "position_ids": [],
                }
                imports[row["import_id"]] = entry
            if row["gp_id"] is not None:
                entry["position_ids"].append(row["gp_id"])

        snapshots: list[AssetSnapshot] = []
        for entry in imports.values():
            values: list[AssetValuation] = []
            for position_id in entry["position_ids"]:
                values.extend(valuations.get(position_id, []))
            snapshots.append(
                AssetSnapshot(
                    holder=entry["source"],
                    moment=_parse_datetime(entry["date"]),
                    valuations=values,
                )
            )
        return snapshots

    @staticmethod
    def _selected_crypto_wallet_ids(
        assets: list[GainsAssetFilter],
    ) -> Optional[set[UUID]]:
        crypto_filters = [
            asset for asset in assets if asset.product_type == ProductType.CRYPTO
        ]
        if not crypto_filters or any(not asset.wallet_ids for asset in crypto_filters):
            return None
        return {wallet_id for asset in crypto_filters for wallet_id in asset.wallet_ids}

    @staticmethod
    def _product_types(assets: list[GainsAssetFilter]) -> list[str]:
        return sorted({asset.product_type.value for asset in assets})

    @staticmethod
    def _deduplicate_factoring_flows(flows: list[GainsFlow]) -> list[GainsFlow]:
        unique_flows: list[GainsFlow] = []
        seen: set[tuple] = set()
        for flow in flows:
            if flow.product_type != ProductType.FACTORING or not flow.holder.endswith(
                "|REAL"
            ):
                unique_flows.append(flow)
                continue
            fingerprint = (
                flow.holder,
                flow.asset_key,
                flow.moment,
                flow.transaction_type,
                flow.amount,
                flow.currency,
                flow.quantity,
                flow.net_amount,
                flow.fees,
                flow.retentions,
            )
            if fingerprint not in seen:
                seen.add(fingerprint)
                unique_flows.append(flow)
        return unique_flows
