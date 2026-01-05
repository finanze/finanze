from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
from typing import Callable, Dict, Optional
from uuid import UUID

from application.ports.auto_contributions_port import AutoContributionsPort
from application.ports.entity_port import EntityPort
from application.ports.pending_flow_port import PendingFlowPort
from application.ports.periodic_flow_port import PeriodicFlowPort
from application.ports.position_port import PositionPort
from application.ports.real_estate_port import RealEstatePort
from dateutil.relativedelta import relativedelta
from domain.auto_contributions import (
    ContributionFrequency,
    ContributionQueryRequest,
    ContributionTargetType,
    PeriodicContribution,
)
from domain.constants import CAPITAL_GAINS_BASE_TAX
from domain.dezimal import Dezimal
from domain.earnings_expenses import FlowFrequency, FlowType
from domain.forecast import (
    CashDelta,
    ForecastRequest,
    ForecastResult,
    RealEstateEquityForecast,
)
from domain.global_position import (
    Accounts,
    AccountType,
    CryptoCurrencies,
    Deposits,
    EntitiesPosition,
    FactoringInvestments,
    FundInvestments,
    FundPortfolios,
    GlobalPosition,
    ProductType,
    RealEstateCFInvestments,
    StockInvestments,
)
from domain.real_estate import RealEstate, RealEstateFlowSubtype
from domain.use_cases.forecast import Forecast


def _calculate_value_increase(from_date: date, to_date: date, annual_increase: Dezimal):
    if annual_increase is None or annual_increase <= Dezimal(0):
        return Dezimal(0)
    months_delta = relativedelta(to_date, from_date)
    months = (
        months_delta.years * 12
        + months_delta.months
        + (1 if months_delta.days > 0 else 0)
    )
    if months <= 0:
        return Dezimal(0)
    monthly_increase = Dezimal(1) + (annual_increase / 12)
    v = Dezimal(1)
    for _ in range(months):
        v = v * monthly_increase
    return v - Dezimal(1)


class ForecastImpl(Forecast):
    def __init__(
        self,
        position_port: PositionPort,
        auto_contributions_port: AutoContributionsPort,
        periodic_flow_port: PeriodicFlowPort,
        pending_flow_port: PendingFlowPort,
        real_estate_port: RealEstatePort,
        entity_port: EntityPort,
    ) -> None:
        self._position_port = position_port
        self._auto_contributions_port = auto_contributions_port
        self._periodic_flow_port = periodic_flow_port
        self._pending_flow_port = pending_flow_port
        self._real_estate_port = real_estate_port
        self._entity_port = entity_port

    # ---------- Helpers for occurrences ----------
    def _advance_after_today(
        self, start: date, every: FlowFrequency, today: date
    ) -> date:
        if every == FlowFrequency.DAILY:
            return today + timedelta(days=1)
        if every == FlowFrequency.WEEKLY:
            days_since = (today - start).days
            weeks_passed = days_since // 7
            candidate = start + timedelta(weeks=weeks_passed + 1)
            return (
                candidate
                if candidate > today
                else start + timedelta(weeks=weeks_passed + 2)
            )
        # Monthly-based frequencies
        months_map = {
            FlowFrequency.EVERY_TWO_MONTHS: 2,
            FlowFrequency.MONTHLY: 1,
            FlowFrequency.QUARTERLY: 3,
            FlowFrequency.EVERY_FOUR_MONTHS: 4,
            FlowFrequency.SEMIANNUALLY: 6,
            FlowFrequency.YEARLY: 12,
        }
        if every in months_map:
            step = months_map[every]
            nxt = start
            while nxt <= today:
                nxt = nxt + relativedelta(months=step)
            return nxt
        # Fallback to avoid None
        return today + timedelta(days=1)

    def _add_step(self, current: date, every: FlowFrequency) -> date:
        if every == FlowFrequency.DAILY:
            return current + timedelta(days=1)
        if every == FlowFrequency.WEEKLY:
            return current + timedelta(weeks=1)
        months_map = {
            FlowFrequency.EVERY_TWO_MONTHS: 2,
            FlowFrequency.MONTHLY: 1,
            FlowFrequency.QUARTERLY: 3,
            FlowFrequency.EVERY_FOUR_MONTHS: 4,
            FlowFrequency.SEMIANNUALLY: 6,
            FlowFrequency.YEARLY: 12,
        }
        if every in months_map:
            return current + relativedelta(months=months_map[every])
        return current

    def _count_periodic_occurrences(
        self, start: date, every: FlowFrequency, until: Optional[date], target: date
    ) -> int:
        if start > target:
            return 0
        if until and start > until:
            return 0
        today = date.today()
        first = start
        if first <= today:
            first = self._advance_after_today(start, every, today)
        if until and first > until:
            return 0
        count = 0
        current = first
        while current <= target and (not until or current <= until):
            count += 1
            current = self._add_step(current, every)
        return count

    def _count_biweekly(self, start: date, until: Optional[date], target: date) -> int:
        if start > target:
            return 0
        today = date.today()
        first = start
        if first <= today:
            days_since = (today - start).days
            weeks_interval = 2
            periods_passed = days_since // (weeks_interval * 7)
            first = start + timedelta(weeks=(periods_passed + 1) * weeks_interval)
            if first <= today:
                first = start + timedelta(weeks=(periods_passed + 2) * weeks_interval)
        if until and first > until:
            return 0
        count = 0
        current = first
        while current <= target and (not until or current <= until):
            count += 1
            current = current + timedelta(weeks=2)
        return count

    def _count_contrib_occurrences(
        self,
        start: date,
        freq: ContributionFrequency,
        until: Optional[date],
        target: date,
    ) -> int:
        mapping = {
            ContributionFrequency.WEEKLY: FlowFrequency.WEEKLY,
            ContributionFrequency.MONTHLY: FlowFrequency.MONTHLY,
            ContributionFrequency.BIMONTHLY: FlowFrequency.EVERY_TWO_MONTHS,
            ContributionFrequency.EVERY_FOUR_MONTHS: FlowFrequency.EVERY_FOUR_MONTHS,
            ContributionFrequency.QUARTERLY: FlowFrequency.QUARTERLY,
            ContributionFrequency.SEMIANNUAL: FlowFrequency.SEMIANNUALLY,
            ContributionFrequency.YEARLY: FlowFrequency.YEARLY,
        }
        if freq == ContributionFrequency.BIWEEKLY:
            return self._count_biweekly(start, until, target)
        if freq in mapping:
            return self._count_periodic_occurrences(start, mapping[freq], until, target)
        return 0

    # ---------- Cash delta from pending and periodic flows ----------
    async def _linked_real_estate_periodic_ids(self) -> set:
        ids: set = set()
        all_re = await self._real_estate_port.get_all()
        for re in all_re:
            for f in re.flows:
                if f.periodic_flow_id is not None:
                    ids.add(f.periodic_flow_id)
        return ids

    async def _build_cash_delta_from_flows(self, target: date) -> Dict[str, Dezimal]:
        today = date.today()
        cash_delta: Dict[str, Dezimal] = {}
        # Pending flows
        pending_flows = await self._pending_flow_port.get_all()
        for pf in pending_flows:
            if not pf.enabled:
                continue
            when = pf.date or today
            if when > target:
                continue
            sign = (
                Dezimal(1)
                if pf.flow_type.name == FlowType.EARNING.name
                else Dezimal(-1)
            )
            cash_delta[pf.currency] = (
                cash_delta.get(pf.currency, Dezimal(0)) + sign * pf.amount
            )
        # Periodic flows (exclude linked flows)
        linked_ids = await self._linked_real_estate_periodic_ids()
        periodic_flows = await self._periodic_flow_port.get_all()
        for flow in periodic_flows:
            if not flow.enabled:
                continue
            if flow.id in linked_ids:
                continue
            count = self._count_periodic_occurrences(
                flow.since, flow.frequency, flow.until, target
            )
            if count <= 0:
                continue
            sign = (
                Dezimal(1)
                if flow.flow_type.name == FlowType.EARNING.name
                else Dezimal(-1)
            )
            total = sign * flow.amount * Dezimal(count)
            cash_delta[flow.currency] = (
                cash_delta.get(flow.currency, Dezimal(0)) + total
            )
        return cash_delta

    # ---------- Real estate cash delta (income/costs/loans and taxes) ----------
    def _monthly_equivalent(self, amount: Dezimal, freq: FlowFrequency) -> Dezimal:
        # Replicate frontend mapping for monthly costs normalization
        if freq == FlowFrequency.DAILY:
            return amount * Dezimal("30")
        if freq == FlowFrequency.WEEKLY:
            return amount * Dezimal("4.33")
        if freq == FlowFrequency.EVERY_TWO_MONTHS:
            return amount / Dezimal("2")
        if freq == FlowFrequency.QUARTERLY:
            return amount / Dezimal("3")
        if freq == FlowFrequency.EVERY_FOUR_MONTHS:
            return amount / Dezimal("4")
        if freq == FlowFrequency.SEMIANNUALLY:
            return amount / Dezimal("6")
        if freq == FlowFrequency.YEARLY:
            return amount / Dezimal("12")
        # MONTHLY and others default to identity
        return amount

    async def _add_real_estate_cash_delta(
        self, target: date, cash_delta: Dict[str, Dezimal]
    ) -> None:
        today = date.today()
        months_delta = relativedelta(target, today)
        steps = (
            months_delta.years * 12
            + months_delta.months
            + (1 if months_delta.days > 0 else 0)
        )
        if steps <= 0:
            return
        real_estates: list[RealEstate] = await self._real_estate_port.get_all()
        for re in real_estates:
            currency = re.currency
            # Totals based on occurrences until target (income/costs/loan payments)
            total_income = Dezimal(0)
            total_costs = Dezimal(0)
            total_loan_pay = Dezimal(0)
            # Monthly values for tax computation
            monthly_costs = Dezimal(0)
            monthly_income_gross = Dezimal(0)
            monthly_loan_payments = Dezimal(0)
            monthly_loan_interests = Dezimal(0)

            for f in re.flows:
                pf = f.periodic_flow
                if f.flow_subtype == RealEstateFlowSubtype.RENT:
                    if pf and pf.amount is not None:
                        # Occurrence-based for cash
                        occ = self._count_periodic_occurrences(
                            pf.since, pf.frequency, pf.until, target
                        )
                        if occ > 0:
                            total_income = total_income + pf.amount * Dezimal(occ)
                        # Monthly baseline for taxes (frontend assumes monthly; no freq normalization)
                        monthly_income_gross = monthly_income_gross + pf.amount
                elif f.flow_subtype in (
                    RealEstateFlowSubtype.COST,
                    RealEstateFlowSubtype.SUPPLY,
                ):
                    if pf and pf.amount is not None:
                        occ = self._count_periodic_occurrences(
                            pf.since, pf.frequency, pf.until, target
                        )
                        if occ > 0:
                            total_costs = total_costs + pf.amount * Dezimal(occ)
                        # Monthly cost normalized by frequency
                        monthly_costs = monthly_costs + self._monthly_equivalent(
                            pf.amount, pf.frequency
                        )
                elif f.flow_subtype == RealEstateFlowSubtype.LOAN:
                    if pf and pf.amount is not None:
                        occ = self._count_periodic_occurrences(
                            pf.since, pf.frequency, pf.until, target
                        )
                        if occ > 0:
                            total_loan_pay = total_loan_pay + pf.amount * Dezimal(occ)
                        monthly_loan_payments = monthly_loan_payments + pf.amount
                    payload = getattr(f, "payload", None)
                    if (
                        payload is not None
                        and getattr(payload, "monthly_interests", None) is not None
                    ):
                        monthly_loan_interests = (
                            monthly_loan_interests + payload.monthly_interests
                        )

            # Vacancy rate and marginal tax
            vacancy_rate = (
                re.rental_data.vacancy_rate
                if (re.rental_data and re.rental_data.vacancy_rate is not None)
                else Dezimal(0)
            )
            adj = Dezimal(1) - vacancy_rate
            if adj < Dezimal(0):
                adj = Dezimal(0)
            monthly_income = monthly_income_gross * adj

            # Tax deductible monthly
            # Flow costs deductible only if flagged
            flow_costs_deductible = Dezimal(0)
            for f in re.flows:
                if f.flow_subtype in (
                    RealEstateFlowSubtype.COST,
                    RealEstateFlowSubtype.SUPPLY,
                ):
                    payload = getattr(f, "payload", None)
                    if payload is not None and getattr(
                        payload, "tax_deductible", False
                    ):
                        pf = f.periodic_flow
                        if pf and pf.amount is not None:
                            flow_costs_deductible = (
                                flow_costs_deductible
                                + self._monthly_equivalent(pf.amount, pf.frequency)
                            )
            monthly_amorts = Dezimal(0)
            if re.rental_data and re.rental_data.amortizations:
                for a in re.rental_data.amortizations:
                    if a.amount is not None:
                        monthly_amorts = monthly_amorts + (a.amount / Dezimal(12))

            monthly_tax_deductible_raw = (
                flow_costs_deductible + monthly_loan_interests + monthly_amorts
            )
            taxable_base_monthly = (
                monthly_income if monthly_income > Dezimal(0) else Dezimal(0)
            )
            monthly_tax_deductible = (
                monthly_tax_deductible_raw
                if monthly_tax_deductible_raw <= taxable_base_monthly
                else taxable_base_monthly
            )
            taxable_monthly_for_taxes = monthly_income - monthly_tax_deductible
            if taxable_monthly_for_taxes < Dezimal(0):
                taxable_monthly_for_taxes = Dezimal(0)
            marginal_rate = (
                re.rental_data.marginal_tax_rate
                if (re.rental_data and re.rental_data.marginal_tax_rate is not None)
                else Dezimal(0)
            )
            # Clamp marginal_rate to non-negative to avoid negative taxes
            if marginal_rate < Dezimal(0):
                marginal_rate = Dezimal(0)
            taxes_monthly = taxable_monthly_for_taxes * marginal_rate
            # Final safety: taxes cannot be negative
            if taxes_monthly < Dezimal(0):
                taxes_monthly = Dezimal(0)

            # Net cash from real estate flows and taxes
            net_cash = (
                monthly_income - monthly_costs - monthly_loan_payments - taxes_monthly
            ) * Dezimal(steps)
            if net_cash != Dezimal(0):
                cash_delta[currency] = cash_delta.get(currency, Dezimal(0)) + net_cash

    # ---------- Contributions ----------
    async def _apply_auto_contributions(
        self,
        target: date,
        forecast_positions: Dict[str, GlobalPosition],
        excluded_entities: Optional[list[UUID]],
        cash_delta: Dict[str, Dezimal],
    ) -> None:
        contrib_map = await self._auto_contributions_port.get_all_grouped_by_entity(
            ContributionQueryRequest(excluded_entities=excluded_entities)
        )
        for entity, contribs in contrib_map.items():
            entity_id = str(entity.id)
            gp = forecast_positions.get(entity_id)
            if not gp:
                continue
            for pc in contribs.periodic:
                if not pc.active:
                    continue
                occ = self._count_contrib_occurrences(
                    pc.since, pc.frequency, pc.until, target
                )
                if occ <= 0:
                    continue
                total = pc.amount * Dezimal(occ)
                # Apply to target position
                self._apply_contribution_to_position(
                    gp, pc.target_type, pc.target, total
                )
                # Subtract cash from cash_delta in the contribution currency
                cash_delta[pc.currency] = (
                    cash_delta.get(pc.currency, Dezimal(0)) - total
                )

    def _apply_contribution_to_position(
        self,
        gp: GlobalPosition,
        target_type: ContributionTargetType,
        target: Optional[str],
        total: Dezimal,
    ) -> None:
        handlers: dict[
            ContributionTargetType,
            Callable[[GlobalPosition, Optional[str], Dezimal], None],
        ] = {
            ContributionTargetType.STOCK_ETF: self._apply_stock_contribution,
            ContributionTargetType.FUND: self._apply_fund_contribution,
            ContributionTargetType.FUND_PORTFOLIO: self._apply_fund_portfolio_contribution,
            ContributionTargetType.CRYPTO: self._apply_crypto_contribution,
        }
        fn = handlers.get(target_type)
        if fn:
            fn(gp, target, total)

    def _apply_stock_contribution(
        self, gp: GlobalPosition, target: Optional[str], total: Dezimal
    ) -> None:
        if ProductType.STOCK_ETF not in gp.products:
            return
        stock_inv: StockInvestments = gp.products[ProductType.STOCK_ETF]
        for s in stock_inv.entries:
            if getattr(s, "isin", None) == target:
                s.initial_investment = s.initial_investment + total
                s.market_value = s.market_value + total
                return

    def _apply_fund_contribution(
        self, gp: GlobalPosition, target: Optional[str], total: Dezimal
    ) -> None:
        if ProductType.FUND not in gp.products:
            return
        fund_inv: FundInvestments = gp.products[ProductType.FUND]
        for f in fund_inv.entries:
            if getattr(f, "isin", None) == target:
                f.initial_investment = f.initial_investment + total
                f.market_value = f.market_value + total
                return

    def _apply_fund_portfolio_contribution(
        self, gp: GlobalPosition, target: Optional[str], total: Dezimal
    ) -> None:
        # Try to allocate proportionally to funds linked to the portfolio identified by target IBAN
        if target is None:
            return
        if ProductType.ACCOUNT not in gp.products:
            return
        accounts: Accounts = gp.products[ProductType.ACCOUNT]
        acc_match = None
        for acc in accounts.entries:
            if acc.type.name == "FUND_PORTFOLIO" and acc.iban == target:
                acc_match = acc
                break
        if acc_match is None:
            return
        # Find portfolio linked to this account
        portfolio = None
        if ProductType.FUND_PORTFOLIO in gp.products:
            portfolios: FundPortfolios = gp.products[ProductType.FUND_PORTFOLIO]
            for p in portfolios.entries:
                # Match either by account_id or by nested account IBAN when available
                if (p.account_id and p.account_id == acc_match.id) or (
                    getattr(p, "account", None) is not None
                    and getattr(p.account, "iban", None) == target
                ):
                    portfolio = p
                    break
        # Find funds tied to the portfolio
        funds_for_portfolio = []
        total_mv = Dezimal(0)
        if portfolio is not None and ProductType.FUND in gp.products:
            fund_inv: FundInvestments = gp.products[ProductType.FUND]
            for f in fund_inv.entries:
                if getattr(f, "portfolio", None) is not None and getattr(
                    f.portfolio, "id", None
                ) == getattr(portfolio, "id", None):
                    funds_for_portfolio.append(f)
                    total_mv = total_mv + (f.market_value or Dezimal(0))
        # If we can distribute, do it proportionally; otherwise fallback to account cash
        if portfolio is not None and funds_for_portfolio and total_mv > Dezimal(0):
            for f in funds_for_portfolio:
                weight = (f.market_value or Dezimal(0)) / total_mv
                inc = total * weight
                f.initial_investment = f.initial_investment + inc
                f.market_value = f.market_value + inc
            # Update portfolio totals
            portfolio.initial_investment = (
                portfolio.initial_investment or Dezimal(0)
            ) + total
            portfolio.market_value = (portfolio.market_value or Dezimal(0)) + total
            return
        # Fallback: add to related account cash as before
        acc_match.total = acc_match.total + total

    def _apply_crypto_contribution(
        self, gp: GlobalPosition, target: Optional[str], total: Dezimal
    ) -> None:
        if not target or ProductType.CRYPTO not in gp.products:
            return
        wallets: CryptoCurrencies = gp.products[ProductType.CRYPTO]
        norm_target = target.upper()
        for wallet in wallets.entries:
            for asset in getattr(wallet, "assets", []):
                symbol = getattr(asset, "symbol", None)
                contract = getattr(asset, "contract_address", None)
                match_symbol = symbol is not None and symbol.upper() == norm_target
                match_contract = contract is not None and contract == target
                if not (match_symbol or match_contract):
                    continue
                base_init = asset.initial_investment or Dezimal(0)
                base_mv = asset.market_value or Dezimal(0)
                current_amount = asset.amount or Dezimal(0)
                unit_price: Optional[Dezimal] = None
                if asset.market_value and asset.amount and asset.amount > Dezimal(0):
                    unit_price = asset.market_value / asset.amount
                asset.initial_investment = base_init + total
                asset.market_value = base_mv + total
                if unit_price and unit_price > Dezimal(0):
                    amount_inc = total / unit_price
                    asset.amount = current_amount + amount_inc
                return

    # ---------- Liquidation helpers ----------
    def _preferred_account(self, gp: GlobalPosition, currency: str):
        if ProductType.ACCOUNT not in gp.products:
            return None
        accounts: Accounts = gp.products[ProductType.ACCOUNT]
        priority = [
            AccountType.VIRTUAL_WALLET,
            AccountType.CHECKING,
            AccountType.BROKERAGE,
            AccountType.SAVINGS,
        ]
        # First try same currency
        by_type = {t: [] for t in priority}
        for acc in accounts.entries:
            if acc.currency == currency and acc.type in by_type:
                by_type[acc.type].append(acc)
        for t in priority:
            if by_type[t]:
                return by_type[t][0]
        # Fallback any currency
        by_type_any = {t: [] for t in priority}
        for acc in accounts.entries:
            if acc.type in by_type_any:
                by_type_any[acc.type].append(acc)
        for t in priority:
            if by_type_any[t]:
                return by_type_any[t][0]
        return None

    def _add_cash_to_account_or_delta(
        self,
        gp: GlobalPosition,
        currency: str,
        amount: Dezimal,
        cash_delta: Dict[str, Dezimal],
    ) -> None:
        acc = self._preferred_account(gp, currency)
        if acc is not None:
            acc.total = acc.total + amount
        else:
            cash_delta[currency] = cash_delta.get(currency, Dezimal(0)) + amount

    def _liquidate_maturing_investments(
        self,
        forecast_positions: Dict[str, GlobalPosition],
        target: date,
        cash_delta: Dict[str, Dezimal],
    ) -> None:
        for gp in forecast_positions.values():
            self._liquidate_deposits(gp, target, cash_delta)
            self._liquidate_factoring(gp, target, cash_delta)
            self._liquidate_recf(gp, target, cash_delta)

    def _net_profit(self, profit: Optional[Dezimal]) -> Dezimal:
        if profit is None or profit <= Dezimal(0):
            return Dezimal(0)
        return profit * (Dezimal(1) - CAPITAL_GAINS_BASE_TAX)

    def _liquidate_deposits(
        self, gp: GlobalPosition, target: date, cash_delta: Dict[str, Dezimal]
    ) -> None:
        if ProductType.DEPOSIT not in gp.products:
            return
        deposits: Deposits = gp.products[ProductType.DEPOSIT]
        remaining: list = []
        for d in deposits.entries:
            if d.maturity and d.maturity <= target:
                profit = (
                    d.expected_interests
                    if d.expected_interests is not None
                    else Dezimal(0)
                )
                payout = d.amount + self._net_profit(profit)
                self._add_cash_to_account_or_delta(gp, d.currency, payout, cash_delta)
            else:
                remaining.append(d)
        deposits.entries = remaining

    def _liquidate_factoring(
        self, gp: GlobalPosition, target: date, cash_delta: Dict[str, Dezimal]
    ) -> None:
        if ProductType.FACTORING not in gp.products:
            return
        factoring: FactoringInvestments = gp.products[ProductType.FACTORING]
        remaining: list = []
        for f in factoring.entries:
            if f.maturity and f.maturity <= target:
                # Prefer profitability; fall back to interest_rate
                rate = None
                if f.profitability is not None:
                    rate = f.profitability
                else:
                    rate = f.interest_rate
                profit = f.amount * rate if rate is not None else Dezimal(0)
                payout = f.amount + self._net_profit(profit)
                self._add_cash_to_account_or_delta(gp, f.currency, payout, cash_delta)
            else:
                remaining.append(f)
        factoring.entries = remaining

    def _liquidate_recf(
        self, gp: GlobalPosition, target: date, cash_delta: Dict[str, Dezimal]
    ) -> None:
        if ProductType.REAL_ESTATE_CF not in gp.products:
            return
        recf: RealEstateCFInvestments = gp.products[ProductType.REAL_ESTATE_CF]
        remaining: list = []
        for r in recf.entries:
            if r.maturity <= target:
                rate = (
                    r.profitability if r.profitability is not None else r.interest_rate
                )
                profit = r.amount * rate if rate is not None else Dezimal(0)
                payout = r.amount + self._net_profit(profit)
                self._add_cash_to_account_or_delta(gp, r.currency, payout, cash_delta)
            else:
                remaining.append(r)
        recf.entries = remaining

    # ---------- Real estate equity forecast ----------
    def _apply_appreciation(
        self, value: Dezimal, months: int, annual_appr: Optional[Dezimal]
    ) -> Dezimal:
        if annual_appr is None or months <= 0:
            return value
        monthly_appr = Dezimal(1) + (annual_appr / 12)
        v = value
        for _ in range(months):
            v = v * monthly_appr
        return v

    def _compute_annual_rate(
        self,
        interest_type: Optional[str],
        annual_rate_base: Optional[Dezimal],
        euribor: Optional[Dezimal],
        fixed_years: Optional[int],
        start: Optional[date],
        cur_date: date,
    ) -> Dezimal:
        base = annual_rate_base or Dezimal(0)
        if interest_type == "FIXED":
            return base
        if interest_type == "VARIABLE":
            return base + (euribor or Dezimal(0))
        # MIXED or unknown
        if fixed_years is not None and start is not None:
            fixed_end = start + relativedelta(years=fixed_years)
            if cur_date < fixed_end:
                return base
        return base + (euribor or Dezimal(0))

    def _simulate_loan_outstanding(
        self,
        outstanding_now: Dezimal,
        payment: Optional[Dezimal],
        start: Optional[date],
        interest_type: Optional[str],
        annual_rate_base: Optional[Dezimal],
        euribor: Optional[Dezimal],
        fixed_years: Optional[int],
        months: int,
        today: date,
    ) -> Dezimal:
        # Safeguards: never allow negative starting outstanding
        if outstanding_now < Dezimal(0):
            outstanding_now = Dezimal(0)
        if months <= 0 or payment is None or start is None:
            return outstanding_now
        outstanding = outstanding_now
        cur_date = today
        for _ in range(max(0, months)):
            annual = self._compute_annual_rate(
                interest_type, annual_rate_base, euribor, fixed_years, start, cur_date
            )
            # Clamp negative rates to zero to avoid increasing outstanding via negative interest side-effects
            if annual < Dezimal(0):
                annual = Dezimal(0)
            monthly_rate = annual / 12
            interest = outstanding * monthly_rate
            principal_paid = payment - interest
            # Do not allow negative amortization (principal increase) in this simplified forecast
            if principal_paid < Dezimal(0):
                principal_paid = Dezimal(0)
            # Cap principal payment to remaining outstanding
            if principal_paid > outstanding:
                principal_paid = outstanding
            outstanding = outstanding - principal_paid
            if outstanding < Dezimal(0):  # final guard
                outstanding = Dezimal(0)
            cur_date = cur_date + relativedelta(months=1)
            if outstanding == Dezimal(0):
                break
        return outstanding

    def _equity_for_property(
        self, re: RealEstate, today: date, months: int
    ) -> Optional[RealEstateEquityForecast]:
        if not re.valuation_info or re.valuation_info.estimated_market_value is None:
            return None
        mkt_now = re.valuation_info.estimated_market_value
        if mkt_now < Dezimal(0):  # sanitize improbable negative valuation
            mkt_now = Dezimal(0)
        mkt_target = self._apply_appreciation(
            mkt_now, months, re.valuation_info.annual_appreciation
        )

        outstanding_now_total = Dezimal(0)
        outstanding_target_total = Dezimal(0)
        for flow in re.flows:
            if flow.flow_subtype != RealEstateFlowSubtype.LOAN:
                continue
            payload = getattr(flow, "payload", None)
            if not payload or not hasattr(payload, "principal_outstanding"):
                continue
            outstanding_now = payload.principal_outstanding or Dezimal(0)
            if outstanding_now < Dezimal(0):
                outstanding_now = Dezimal(0)
            outstanding_now_total = outstanding_now_total + outstanding_now

            payment: Optional[Dezimal] = None
            start: Optional[date] = None
            if flow.periodic_flow:
                payment = flow.periodic_flow.amount
                start = flow.periodic_flow.since

            outstanding_target = self._simulate_loan_outstanding(
                outstanding_now=outstanding_now,
                payment=payment,
                start=start,
                interest_type=payload.interest_type.name
                if getattr(payload, "interest_type", None) is not None
                else None,
                annual_rate_base=getattr(payload, "interest_rate", None),
                euribor=getattr(payload, "euribor_rate", None),
                fixed_years=getattr(payload, "fixed_years", None),
                months=months,
                today=today,
            )
            if outstanding_target < Dezimal(0):
                outstanding_target = Dezimal(0)
            outstanding_target_total = outstanding_target_total + outstanding_target

        equity_now = mkt_now - outstanding_now_total
        equity_target = mkt_target - outstanding_target_total
        return RealEstateEquityForecast(
            id=re.id,
            equity_now=equity_now,
            equity_at_target=equity_target,
            principal_outstanding_now=outstanding_now_total,
            principal_outstanding_at_target=outstanding_target_total,
            currency=re.currency,
        )

    async def _forecast_real_estate_equity(
        self, target: date
    ) -> list[RealEstateEquityForecast]:
        today = date.today()
        real_estate: list[RealEstate] = await self._real_estate_port.get_all()
        months_delta = relativedelta(target, today)
        months = (
            months_delta.years * 12
            + months_delta.months
            + (1 if months_delta.days > 0 else 0)
        )
        results: list[RealEstateEquityForecast] = []
        for re in real_estate:
            eq = self._equity_for_property(re, today, months)
            if eq is not None:
                results.append(eq)
        return results

    # ---------- Monthly revaluation and contributions ----------
    def _iter_contrib_dates(self, pc: PeriodicContribution, target: date) -> list[date]:
        dates: list[date] = []
        today = date.today()
        if not pc.active:
            return dates
        if pc.since > target:
            return dates
        until = pc.until
        # For weekly-like
        if pc.frequency == ContributionFrequency.BIWEEKLY:
            # find first after today
            first = pc.since
            if first <= today:
                days_since = (today - pc.since).days
                weeks_interval = 2
                periods_passed = days_since // (weeks_interval * 7)
                first = pc.since + timedelta(
                    weeks=(periods_passed + 1) * weeks_interval
                )
                if first <= today:
                    first = pc.since + timedelta(
                        weeks=(periods_passed + 2) * weeks_interval
                    )
            cur = first
            while cur <= target and (not until or cur <= until):
                dates.append(cur)
                cur = cur + timedelta(weeks=2)
            return dates
        # Map remaining to FlowFrequency and reuse helpers
        mapping = {
            ContributionFrequency.WEEKLY: FlowFrequency.WEEKLY,
            ContributionFrequency.MONTHLY: FlowFrequency.MONTHLY,
            ContributionFrequency.BIMONTHLY: FlowFrequency.EVERY_TWO_MONTHS,
            ContributionFrequency.EVERY_FOUR_MONTHS: FlowFrequency.EVERY_FOUR_MONTHS,
            ContributionFrequency.QUARTERLY: FlowFrequency.QUARTERLY,
            ContributionFrequency.SEMIANNUAL: FlowFrequency.SEMIANNUALLY,
            ContributionFrequency.YEARLY: FlowFrequency.YEARLY,
        }
        if pc.frequency not in mapping:
            return dates
        every = mapping[pc.frequency]
        # find first after today
        first = pc.since
        if first <= today:
            first = self._advance_after_today(pc.since, every, today)
        if until and first > until:
            return dates
        cur = first
        while cur <= target and (not until or cur <= until):
            dates.append(cur)
            cur = self._add_step(cur, every)
        return dates

    def _apply_monthly_revaluation_to_equities(
        self, gp: GlobalPosition, monthly_rate: Dezimal
    ) -> None:
        factor = Dezimal(1) + monthly_rate
        if ProductType.STOCK_ETF in gp.products:
            stock_inv: StockInvestments = gp.products[ProductType.STOCK_ETF]
            for s in stock_inv.entries:
                s.market_value = s.market_value * factor
        if ProductType.FUND in gp.products:
            fund_inv: FundInvestments = gp.products[ProductType.FUND]
            for f in fund_inv.entries:
                f.market_value = f.market_value * factor

    async def _simulate_monthly_revaluation_and_contributions(
        self,
        forecast_positions: Dict[str, GlobalPosition],
        target: date,
        avg_increase: Dezimal,
        cash_delta: Dict[str, Dezimal],
        excluded_entities: Optional[list[UUID]],
    ) -> None:
        monthly_rate = avg_increase / Dezimal(12)
        # Build contributions map once
        contrib_map = await self._auto_contributions_port.get_all_grouped_by_entity(
            ContributionQueryRequest(excluded_entities=excluded_entities)
        )
        # Precompute occurrences per entity
        per_entity_occurrences: dict[
            str, list[tuple[PeriodicContribution, list[date]]]
        ] = {}
        for entity, contribs in contrib_map.items():
            entity_id = str(entity.id)
            occs: list[tuple[PeriodicContribution, list[date]]] = []
            for pc in contribs.periodic:
                if not pc.active:
                    continue
                dates = self._iter_contrib_dates(pc, target)
                if dates:
                    occs.append((pc, dates))
            per_entity_occurrences[entity_id] = occs

        # Iterate month by month
        today = date.today()
        months_delta = relativedelta(target, today)
        steps = (
            months_delta.years * 12
            + months_delta.months
            + (1 if months_delta.days > 0 else 0)
        )
        prev_boundary = today
        cur_boundary = today
        for _ in range(max(0, steps)):
            cur_boundary = cur_boundary + relativedelta(months=1)
            for entity_id, gp in forecast_positions.items():
                # Apply contributions due within (prev_boundary, cur_boundary]
                occs = per_entity_occurrences.get(entity_id, [])
                for pc, dates in occs:
                    for d in dates:
                        if prev_boundary < d <= cur_boundary:
                            total = pc.amount
                            self._apply_contribution_to_position(
                                gp, pc.target_type, pc.target, total
                            )
                            cash_delta[pc.currency] = (
                                cash_delta.get(pc.currency, Dezimal(0)) - total
                            )
                # After contributions, apply monthly revaluation to equities
                self._apply_monthly_revaluation_to_equities(gp, monthly_rate)
            prev_boundary = cur_boundary

    # ---------- Portfolio sync helper ----------
    def _sync_fund_portfolios(self, gp: GlobalPosition) -> None:
        if (
            ProductType.FUND_PORTFOLIO not in gp.products
            or ProductType.FUND not in gp.products
        ):
            return
        portfolios: FundPortfolios = gp.products[ProductType.FUND_PORTFOLIO]
        fund_inv: FundInvestments = gp.products[ProductType.FUND]
        sums: dict[Optional[str], tuple[Dezimal, Dezimal]] = {}
        for f in fund_inv.entries:
            pid = getattr(getattr(f, "portfolio", None), "id", None)
            if pid is None:
                continue
            init = f.initial_investment or Dezimal(0)
            mv = f.market_value or Dezimal(0)
            if pid in sums:
                pi, pm = sums[pid]
                sums[pid] = (pi + init, pm + mv)
            else:
                sums[pid] = (init, mv)
        for p in portfolios.entries:
            pid = getattr(p, "id", None)
            if pid in sums:
                init, mv = sums[pid]
                p.initial_investment = init
                p.market_value = mv

    # ---------- Core execute ----------
    async def execute(self, request: ForecastRequest) -> ForecastResult:
        target = request.target_date
        today = date.today()
        if target <= today:
            raise ValueError("target_date must be in the future")

        positions_by_entity = await self._position_port.get_last_grouped_by_entity()
        forecast_positions: Dict[str, GlobalPosition] = {}
        for entity, position in positions_by_entity.items():
            forecast_positions[str(entity.id)] = deepcopy(position)

        # Cash delta (exclude linked periodic flows)
        cash_delta: Dict[str, Dezimal] = await self._build_cash_delta_from_flows(target)
        # Add real estate net cash (including taxes)
        await self._add_real_estate_cash_delta(target, cash_delta)

        # Contributions + revaluation path
        disabled_entities = [
            e.id for e in await self._entity_port.get_disabled_entities()
        ]
        if (
            request.avg_annual_market_increase is not None
            and request.avg_annual_market_increase > Dezimal(0)
        ):
            await self._simulate_monthly_revaluation_and_contributions(
                forecast_positions,
                target,
                request.avg_annual_market_increase,
                cash_delta,
                disabled_entities,
            )
        else:
            await self._apply_auto_contributions(
                target, forecast_positions, disabled_entities, cash_delta
            )

        # Liquidate matured investments
        self._liquidate_maturing_investments(forecast_positions, target, cash_delta)

        # Real estate equity forecast
        re_equity = await self._forecast_real_estate_equity(target)

        # Keep portfolio totals in sync
        for gp in forecast_positions.values():
            self._sync_fund_portfolios(gp)

        cash_delta_list = [
            CashDelta(currency=k, amount=v) for k, v in cash_delta.items()
        ]

        crypto_appreciation = _calculate_value_increase(
            date.today(), target, request.avg_annual_crypto_increase
        )
        commodity_appreciation = _calculate_value_increase(
            date.today(), target, request.avg_annual_commodity_increase
        )

        return ForecastResult(
            target_date=target,
            positions=EntitiesPosition(positions=forecast_positions),
            cash_delta=cash_delta_list,
            real_estate=re_equity,
            crypto_appreciation=crypto_appreciation,
            commodity_appreciation=commodity_appreciation,
        )
