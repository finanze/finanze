from datetime import date, datetime
from typing import Optional
from dateutil.tz import tzlocal
from domain.dezimal import Dezimal


def annualized_profitability(
    interest_rate: Optional[Dezimal],
    start_dt: Optional[datetime],
    maturity: Optional[date],
    extended_maturity: Optional[date] = None,
) -> Dezimal:
    if not (interest_rate is not None and start_dt and maturity):
        return Dezimal(0)
    now = datetime.now(tzlocal())
    end_date = maturity
    if extended_maturity and now.date() >= maturity:
        end_date = extended_maturity
    days = (end_date - start_dt.date()).days
    if days <= 0:
        return Dezimal(0)
    profit = interest_rate * Dezimal(days) / Dezimal(365)
    return Dezimal(round(profit, 4))
