from datetime import date, datetime
from typing import Optional
from dateutil.tz import tzlocal
from domain.dezimal import Dezimal

DAYS_IN_YEAR = Dezimal(365)


def annualized_profitability(
    interest_rate: Optional[Dezimal],
    start_dt: Optional[datetime],
    maturity: Optional[date],
    extended_maturity: Optional[date] = None,
    extended_interest_rate: Optional[Dezimal] = None,
    late_interest_rate: Optional[Dezimal] = None,
) -> Dezimal:
    now = datetime.now(tzlocal()).date()
    total_profit = Dezimal(0)
    has_interest = False

    def _add_interest(rate: Optional[Dezimal], days: int) -> None:
        nonlocal total_profit, has_interest
        if rate is None or days <= 0:
            return
        total_profit = total_profit + (rate * Dezimal(days) / DAYS_IN_YEAR)
        has_interest = True

    start_date = start_dt.date() if start_dt else None

    if interest_rate is not None and start_date and maturity and maturity > start_date:
        _add_interest(interest_rate, (maturity - start_date).days)

    if (
        extended_maturity
        and maturity
        and extended_maturity > maturity
        and now >= maturity
    ):
        _add_interest(
            extended_interest_rate or interest_rate, (extended_maturity - maturity).days
        )

    lateness_anchor = extended_maturity if extended_maturity else maturity
    if late_interest_rate and lateness_anchor and now > lateness_anchor:
        _add_interest(late_interest_rate, (now - lateness_anchor).days)

    if not has_interest:
        return Dezimal(0)

    return round(total_profit, 4)
