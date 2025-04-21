from domain.dezimal import Dezimal
from domain.global_position import GlobalPosition, Investments, StockInvestments, FundInvestments, FactoringInvestments, \
    RealStateCFInvestments, Deposits, Crowdlending


def _add_weighted_interest_rate(total1: Dezimal,
                                interest_rate1: Dezimal,
                                total2: Dezimal,
                                interest_rate2: Dezimal) -> Dezimal:
    return (total1 * interest_rate1 + total2 * interest_rate2) / (total1 + total2)


def _add_stocks(self: StockInvestments, other: StockInvestments) -> StockInvestments:
    return StockInvestments(
        investment=(self.investment + other.investment)
        if self.investment and other.investment
        else None,
        market_value=(self.market_value + other.market_value)
        if self.market_value and other.market_value
        else None,
        details=self.details + other.details,
    )


def _add_funds(self: FundInvestments, other: FundInvestments) -> FundInvestments:
    return FundInvestments(
        investment=(self.investment + other.investment)
        if self.investment and other.investment
        else None,
        market_value=(self.market_value + other.market_value)
        if self.market_value and other.market_value
        else None,
        details=self.details + other.details,
    )


def _add_factoring(self: FactoringInvestments, other: FactoringInvestments) -> FactoringInvestments:
    return FactoringInvestments(
        total=(self.total + other.total)
        if self.total and other.total
        else None,
        weighted_interest_rate=(_add_weighted_interest_rate(self.total, self.weighted_interest_rate, other.total,
                                                            other.weighted_interest_rate))
        if self.weighted_interest_rate and other.weighted_interest_rate
        else None,
        details=self.details + other.details,
    )


def _add_real_state_cf(self: RealStateCFInvestments, other: RealStateCFInvestments) -> RealStateCFInvestments:
    return RealStateCFInvestments(
        total=(self.total + other.total)
        if self.total and other.total
        else None,
        weighted_interest_rate=(_add_weighted_interest_rate(self.total, self.weighted_interest_rate, other.total,
                                                            other.weighted_interest_rate))
        if self.weighted_interest_rate and other.weighted_interest_rate
        else None,
        details=self.details + other.details,
    )


def _add_deposits(self: Deposits, other: Deposits) -> Deposits:
    return Deposits(
        total=(self.total + other.total)
        if self.total and other.total
        else None,
        expected_interests=(self.expected_interests + other.expected_interests)
        if self.expected_interests and other.expected_interests
        else None,
        weighted_interest_rate=(_add_weighted_interest_rate(self.total, self.weighted_interest_rate, other.total,
                                                            other.weighted_interest_rate))
        if self.weighted_interest_rate and other.weighted_interest_rate
        else None,
        details=self.details + other.details,
    )


def _add_crowdlending(self: Crowdlending, other: Crowdlending) -> Crowdlending:
    return Crowdlending(
        id=self.id,
        total=(self.total + other.total)
        if self.total and other.total
        else None,
        weighted_interest_rate=(_add_weighted_interest_rate(self.total, self.weighted_interest_rate, other.total,
                                                            other.weighted_interest_rate))
        if self.weighted_interest_rate and other.weighted_interest_rate
        else None,
        currency=self.currency,
        distribution=self.distribution,
        details=self.details + other.details,
    )


def _add_investments(self: Investments, other: Investments) -> Investments:
    if other is None:
        return self

    return Investments(
        stocks=(self.stocks + other.stocks)
        if self.stocks and other.stocks
        else None,
        funds=(self.funds + other.funds)
        if self.funds and other.funds
        else None,
        factoring=(self.factoring + other.factoring)
        if self.factoring and other.factoring
        else None,
        real_state_cf=(self.real_state_cf + other.real_state_cf)
        if self.real_state_cf and other.real_state_cf
        else None,
        deposits=(self.deposits + other.deposits)
        if self.deposits and other.deposits
        else None,
        crowdlending=(self.crowdlending + other.crowdlending)
        if self.crowdlending and other.crowdlending
        else None,
    )


def _sum_inv(self, attr: str, other: GlobalPosition):
    self_val = getattr(self.investments, attr)
    other_val = getattr(other.investments, attr)
    return (self_val + other_val) if (self_val is not None and other_val is not None) else None


def _add_position(self: GlobalPosition, other: GlobalPosition) -> GlobalPosition:
    if other is None:
        return self

    if self.entity != other.entity:
        raise TypeError(
            f'Tried to add {self.entity} position to '
            f'{other.entity} position',
        )

    return GlobalPosition(
        id=self.id,
        entity=self.entity,
        date=self.date,
        accounts=self.accounts + other.accounts,
        cards=self.cards + other.cards,
        loans=self.loans + other.loans,
        investments=Investments(
            stocks=_sum_inv(self, 'stocks', other),
            funds=_sum_inv(self, 'funds', other),
            factoring=_sum_inv(self, 'factoring', other),
            real_state_cf=_sum_inv(self, 'real_state_cf', other),
            deposits=_sum_inv(self, 'deposits', other),
            crowdlending=_sum_inv(self, 'crowdlending', other),
        ),
        is_real=self.is_real,
    )


StockInvestments.__add__ = _add_stocks
FundInvestments.__add__ = _add_funds
FactoringInvestments.__add__ = _add_factoring
RealStateCFInvestments.__add__ = _add_real_state_cf
Deposits.__add__ = _add_deposits
Crowdlending.__add__ = _add_crowdlending
Investments.__add__ = _add_investments
GlobalPosition.__add__ = _add_position
