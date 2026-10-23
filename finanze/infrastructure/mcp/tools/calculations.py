from datetime import date
from decimal import Decimal
from typing import Annotated, Optional

from domain.calculations import (
    SavingsCalculationRequest,
    SavingsPeriodicity,
    SavingsRetirementRequest,
    SavingsScenarioRequest,
)
from domain.dezimal import Dezimal
from domain.forecast import ForecastRequest
from domain.global_position import InstallmentFrequency, InterestType
from domain.loan_calculator import LoanCalculationParams
from pydantic import BaseModel, Field

from infrastructure.mcp.registry import ToolRegistry
from infrastructure.mcp.use_cases import McpUseCases

Rate = Annotated[
    Optional[Decimal], Field(description="Annual rate as a fraction, e.g. 0.05 for 5%.")
]


class SavingsScenarioInput(BaseModel):
    id: str = Field(min_length=1, description="Scenario identifier.")
    annual_market_performance: Decimal = Field(
        description="Expected annual return as a fraction, e.g. 0.07 for 7%."
    )
    periodic_contribution: Optional[Decimal] = Field(
        default=None, ge=0, description="Contribution per period."
    )
    target_amount: Optional[Decimal] = Field(
        default=None, gt=0, description="Goal amount to reach."
    )


class SavingsRetirementInput(BaseModel):
    withdrawal_amount: Optional[Decimal] = Field(
        default=None, gt=0, description="Withdrawal per period."
    )
    withdrawal_years: Optional[int] = Field(default=None, gt=0)


def _dezimal(value: Optional[Decimal]) -> Optional[Dezimal]:
    return Dezimal(value) if value is not None else None


def register(registry: ToolRegistry, ucs: McpUseCases):
    @registry.read("Calculate savings", category="calculators")
    async def calculate_savings(
        periodicity: SavingsPeriodicity,
        scenarios: Annotated[
            list[SavingsScenarioInput], Field(min_length=1, max_length=10)
        ],
        base_amount: Annotated[
            Optional[Decimal], Field(ge=0, description="Initial amount.")
        ] = None,
        years: Annotated[Optional[int], Field(gt=0, le=100)] = None,
        retirement: Annotated[
            Optional[SavingsRetirementInput],
            Field(description="Optional withdrawal phase after the saving years."),
        ] = None,
    ):
        """Compound savings calculator. Each scenario provides an expected return and either a periodic contribution or a target amount; the missing values (final amount, needed contribution or years) are computed with a yearly breakdown, plus an optional retirement withdrawal phase."""
        return await ucs.calculate_savings.execute(
            SavingsCalculationRequest(
                base_amount=_dezimal(base_amount),
                years=years,
                periodicity=periodicity,
                scenarios=[
                    SavingsScenarioRequest(
                        scenario_id=s.id,
                        annual_market_performance=Dezimal(s.annual_market_performance),
                        periodic_contribution=_dezimal(s.periodic_contribution),
                        target_amount=_dezimal(s.target_amount),
                    )
                    for s in scenarios
                ],
                retirement=SavingsRetirementRequest(
                    withdrawal_amount=_dezimal(retirement.withdrawal_amount),
                    withdrawal_years=retirement.withdrawal_years,
                )
                if retirement
                else None,
            )
        )

    @registry.read("Calculate loan", category="calculators")
    async def calculate_loan(
        interest_rate: Annotated[
            Decimal,
            Field(
                description="Annual interest rate as a fraction. For VARIABLE and MIXED loans, the spread over Euribor."
            ),
        ],
        interest_type: InterestType,
        start: Annotated[date, Field(description="Loan start date.")],
        end: Annotated[date, Field(description="Loan maturity date.")],
        loan_amount: Annotated[
            Optional[Decimal], Field(gt=0, description="Initial principal.")
        ] = None,
        principal_outstanding: Annotated[
            Optional[Decimal],
            Field(ge=0, description="Current outstanding principal."),
        ] = None,
        euribor_rate: Rate = None,
        fixed_years: Annotated[
            Optional[int], Field(ge=0, description="Fixed period of MIXED loans.")
        ] = None,
        fixed_interest_rate: Rate = None,
        installment_frequency: InstallmentFrequency = InstallmentFrequency.MONTHLY,
    ):
        """Loan calculator: installment amount, interests and principal outstanding for fixed, variable (Euribor + spread) or mixed loans. Provide loan_amount or principal_outstanding."""
        return await ucs.calculate_loan.execute(
            LoanCalculationParams(
                loan_amount=_dezimal(loan_amount),
                interest_rate=Dezimal(interest_rate),
                interest_type=interest_type,
                euribor_rate=_dezimal(euribor_rate),
                fixed_years=fixed_years,
                start=start,
                end=end,
                principal_outstanding=_dezimal(principal_outstanding),
                fixed_interest_rate=_dezimal(fixed_interest_rate),
                installment_frequency=installment_frequency,
            )
        )

    @registry.read("Forecast net worth", category="calculators")
    async def forecast_net_worth(
        target_date: Annotated[date, Field(description="Future date to forecast.")],
        avg_annual_market_increase: Annotated[
            Optional[Decimal],
            Field(
                description="Expected yearly return of stocks and funds, as a fraction."
            ),
        ] = None,
        avg_annual_crypto_increase: Annotated[
            Optional[Decimal], Field(description="Expected yearly crypto return.")
        ] = None,
        avg_annual_commodity_increase: Annotated[
            Optional[Decimal], Field(description="Expected yearly commodity return.")
        ] = None,
        include_real_estate_taxes: bool = True,
    ):
        """Forecast the net worth and cash at a future date, applying periodic and pending flows, contributions, loan amortizations, fixed income maturities, real estate appreciation and the given expected returns."""
        return await ucs.forecast.execute(
            ForecastRequest(
                target_date=target_date,
                avg_annual_market_increase=_dezimal(avg_annual_market_increase),
                avg_annual_crypto_increase=_dezimal(avg_annual_crypto_increase)
                or Dezimal(0),
                avg_annual_commodity_increase=_dezimal(avg_annual_commodity_increase)
                or Dezimal(0),
                include_real_estate_taxes=include_real_estate_taxes,
            )
        )
