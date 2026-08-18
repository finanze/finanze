from dataclasses import field
from datetime import date, datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from domain.commodity import CommodityType, WeightUnit
from domain.dezimal import Dezimal
from domain.global_position import EquityType, ProductType
from domain.transactions import TxType
from pydantic.dataclasses import dataclass


GAINS_PRODUCT_TYPES = frozenset(
    {
        ProductType.STOCK_ETF,
        ProductType.FUND,
        ProductType.CRYPTO,
        ProductType.COMMODITY,
        ProductType.DEPOSIT,
        ProductType.FACTORING,
        ProductType.REAL_ESTATE_CF,
    }
)


class FixedIncomeAccrual(str, Enum):
    NONE = "NONE"
    NET = "NET"
    GROSS = "GROSS"


class GainsCalculationMode(str, Enum):
    HYBRID = "HYBRID"
    SNAPSHOTS = "SNAPSHOTS"


class GainsMethod(str, Enum):
    HYBRID_VALUE = "HYBRID_VALUE"
    SNAPSHOT_BOOK_BASIS = "SNAPSHOT_BOOK_BASIS"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class GainsBasis(str, Enum):
    NET_CONTRIBUTIONS = "NET_CONTRIBUTIONS"
    BOOK_BASIS = "BOOK_BASIS"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class GainsQuality(str, Enum):
    COMPLETE = "COMPLETE"
    ESTIMATED = "ESTIMATED"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"


class GainsBasisStatus(str, Enum):
    COMPLETE = "COMPLETE"
    PARTIAL_UNKNOWN = "PARTIAL_UNKNOWN"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class GainsFlowProvenance(str, Enum):
    ACTIVITY = "ACTIVITY"
    SETTLEMENT = "SETTLEMENT"
    TRANSFER_PAIR = "TRANSFER_PAIR"
    OPENING_BASIS = "OPENING_BASIS"
    QUANTITY_RESIDUAL = "QUANTITY_RESIDUAL"
    NET_CONTRIBUTION_FALLBACK = "NET_CONTRIBUTION_FALLBACK"
    REPLAYED_POSITIONS = "REPLAYED_POSITIONS"
    UNKNOWN = "UNKNOWN"


@dataclass
class GainsAssetFilter:
    product_type: ProductType
    asset_keys: list[str] = field(default_factory=list)
    portfolio_names: list[str] = field(default_factory=list)
    equity_types: list[EquityType] = field(default_factory=list)
    wallet_ids: list[UUID] = field(default_factory=list)

    def __post_init__(self):
        if self.product_type not in GAINS_PRODUCT_TYPES:
            raise ValueError(
                f"Unsupported gains product type: {self.product_type.value}"
            )
        if self.portfolio_names and self.product_type != ProductType.FUND:
            raise ValueError("Portfolio filters are only supported for funds.")
        if self.equity_types and self.product_type != ProductType.STOCK_ETF:
            raise ValueError(
                "Equity type filters are only supported for stocks and ETFs."
            )
        if self.wallet_ids and self.product_type != ProductType.CRYPTO:
            raise ValueError("Wallet filters are only supported for crypto.")


@dataclass
class GainsTimelineQuery:
    assets: list[GainsAssetFilter]
    base_currency: str = "EUR"
    entities: Optional[list[UUID]] = None
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    accrue_fixed_income: FixedIncomeAccrual = FixedIncomeAccrual.NONE
    calculation_mode: GainsCalculationMode = GainsCalculationMode.HYBRID

    def __post_init__(self):
        if not self.assets:
            raise ValueError("At least one gains asset filter is required")


@dataclass
class AssetValuation:
    product_type: ProductType
    asset_key: str
    currency: str
    market_value: Dezimal
    portfolio_name: Optional[str] = None
    equity_type: Optional[EquityType] = None
    quantity: Optional[Dezimal] = None
    cost_basis: Optional[Dezimal] = None
    interest_rate: Optional[Dezimal] = None
    start_date: Optional[date] = None
    maturity: Optional[date] = None
    extended_maturity: Optional[date] = None
    extended_interest_rate: Optional[Dezimal] = None
    late_interest_rate: Optional[Dezimal] = None
    commodity_type: Optional[CommodityType] = None
    weight: Optional[Dezimal] = None
    weight_unit: Optional[WeightUnit] = None
    wallet_id: Optional[UUID] = None


@dataclass
class AssetSnapshot:
    holder: str
    moment: datetime
    valuations: list[AssetValuation] = field(default_factory=list)
    holder_deleted_at: Optional[date] = None


@dataclass
class GainsFlow:
    holder: str
    product_type: ProductType
    asset_key: str
    moment: datetime
    amount: Dezimal
    currency: str
    portfolio_name: Optional[str] = None
    equity_type: Optional[EquityType] = None
    quantity: Optional[Dezimal] = None
    net_amount: Optional[Dezimal] = None
    fees: Dezimal = Dezimal(0)
    retentions: Dezimal = Dezimal(0)
    transaction_type: Optional[TxType] = None
    wallet_id: Optional[UUID] = None
    name: Optional[str] = None


@dataclass
class GainsSettlement:
    holder: str
    product_type: ProductType
    asset_key: str
    moment: datetime
    net_proceeds: Dezimal
    currency: str


@dataclass
class GainsMetrics:
    value: Dezimal = Dezimal(0)
    cost_basis: Dezimal = Dezimal(0)
    net_contributions: Dezimal = Dezimal(0)
    gain: Optional[Dezimal] = None
    period_return: Optional[Dezimal] = None
    index: Optional[Dezimal] = None


@dataclass
class GainsTimelinePoint:
    date: date
    metrics: GainsMetrics
    breakdown: dict[str, GainsMetrics] = field(default_factory=dict)


@dataclass
class GainsTimeline:
    currency: str
    points: list[GainsTimelinePoint] = field(default_factory=list)
    method: GainsMethod = GainsMethod.HYBRID_VALUE
    basis: GainsBasis = GainsBasis.NET_CONTRIBUTIONS
    quality: GainsQuality = GainsQuality.COMPLETE
    basis_status: GainsBasisStatus = GainsBasisStatus.NOT_APPLICABLE
    xirr: Optional[Dezimal] = None
    annualized_xirr: Optional[Dezimal] = None
    opening_value: Optional[Dezimal] = None
    warnings: list[str] = field(default_factory=list)
    not_applicable_reasons: list[str] = field(default_factory=list)
