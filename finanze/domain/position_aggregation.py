from domain.dezimal import Dezimal
from domain.global_position import (
    Crowdlending,
    CryptoCurrencies,
    Deposits,
    FactoringInvestments,
    FundInvestments,
    FundPortfolios,
    GlobalPosition,
    ProductPositions,
    RealEstateCFInvestments,
    StockInvestments,
    Accounts,
    Cards,
    Loans,
)


def _add_weighted_interest_rate(
    total1: Dezimal, interest_rate1: Dezimal, total2: Dezimal, interest_rate2: Dezimal
) -> Dezimal:
    return (total1 * interest_rate1 + total2 * interest_rate2) / (total1 + total2)


def _add_stocks(self: StockInvestments, other: StockInvestments) -> StockInvestments:
    return StockInvestments(
        entries=self.entries + other.entries,
    )


def _add_funds(self: FundInvestments, other: FundInvestments) -> FundInvestments:
    return FundInvestments(
        entries=self.entries + other.entries,
    )


def _add_fund_portfolios(self: FundPortfolios, other: FundPortfolios) -> FundPortfolios:
    return FundPortfolios(
        entries=self.entries + other.entries,
    )


def _add_factoring(
    self: FactoringInvestments, other: FactoringInvestments
) -> FactoringInvestments:
    return FactoringInvestments(
        entries=self.entries + other.entries,
    )


def _add_real_estate_cf(
    self: RealEstateCFInvestments, other: RealEstateCFInvestments
) -> RealEstateCFInvestments:
    return RealEstateCFInvestments(
        entries=self.entries + other.entries,
    )


def _add_deposits(self: Deposits, other: Deposits) -> Deposits:
    return Deposits(
        entries=self.entries + other.entries,
    )


def _add_crowdlending(self: Crowdlending, other: Crowdlending) -> Crowdlending:
    return Crowdlending(
        id=self.id,
        total=(self.total + other.total) if self.total and other.total else None,
        weighted_interest_rate=(
            _add_weighted_interest_rate(
                self.total,
                self.weighted_interest_rate,
                other.total,
                other.weighted_interest_rate,
            )
        )
        if self.weighted_interest_rate and other.weighted_interest_rate
        else None,
        currency=self.currency,
        distribution=self.distribution,
        entries=self.entries + other.entries,
    )


def _add_crypto_currencies(
    self: CryptoCurrencies, other: CryptoCurrencies
) -> CryptoCurrencies:
    return CryptoCurrencies(
        entries=self.entries + other.entries,
    )


def _add_accounts(self: Accounts, other: Accounts) -> Accounts:
    return Accounts(
        entries=self.entries + other.entries,
    )


def _add_cards(self: Cards, other: Cards) -> Cards:
    return Cards(
        entries=self.entries + other.entries,
    )


def _add_loans(self: Loans, other: Loans) -> Loans:
    return Loans(
        entries=self.entries + other.entries,
    )


def _add_products(self: ProductPositions, other: ProductPositions) -> ProductPositions:
    if not other:
        return self
    merged: ProductPositions = {}
    for ptype in set(self) | set(other):
        if ptype in self and ptype in other:
            merged[ptype] = self[ptype] + other[ptype]
        else:
            merged[ptype] = self.get(ptype) or other.get(ptype)
    return merged


def _add_position(self: GlobalPosition, other: GlobalPosition) -> GlobalPosition:
    if other is None:
        return self

    if self.entity != other.entity:
        raise TypeError(
            f"Tried to add {self.entity} position to {other.entity} position",
        )

    return GlobalPosition(
        id=self.id,
        entity=self.entity,
        date=self.date,
        products=_add_products(self.products, other.products),
        source=self.source,
    )


def add_extensions():
    StockInvestments.__add__ = _add_stocks
    FundInvestments.__add__ = _add_funds
    FundPortfolios.__add__ = _add_fund_portfolios
    FactoringInvestments.__add__ = _add_factoring
    RealEstateCFInvestments.__add__ = _add_real_estate_cf
    Deposits.__add__ = _add_deposits
    Crowdlending.__add__ = _add_crowdlending
    CryptoCurrencies.__add__ = _add_crypto_currencies
    Accounts.__add__ = _add_accounts
    Cards.__add__ = _add_cards
    Loans.__add__ = _add_loans
    GlobalPosition.__add__ = _add_position
