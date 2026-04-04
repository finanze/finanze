from application.ports.position_port import PositionPort
from application.ports.real_estate_port import RealEstatePort
from application.use_cases.get_periodic_flows import get_next_date
from domain.earnings_expenses import FlowFrequency
from domain.global_position import INSTALLMENT_TO_FLOW_FREQ
from domain.real_estate import LoanPayload, RealEstate, RealEstateFlowSubtype
from domain.use_cases.list_real_estate import ListRealEstate


class ListRealEstateImpl(ListRealEstate):
    def __init__(self, real_estate_port: RealEstatePort, position_port: PositionPort):
        self._real_estate_port = real_estate_port
        self._position_port = position_port

    async def execute(self) -> list[RealEstate]:
        entries = await self._real_estate_port.get_all()

        for entry in entries:
            for flow in entry.flows:
                if flow.periodic_flow:
                    flow.periodic_flow.next_date = get_next_date(flow.periodic_flow)

        await self._inject_linked_loans(entries)

        return entries

    async def _inject_linked_loans(self, entries: list[RealEstate]):
        hashes = []
        for entry in entries:
            for flow in entry.flows:
                if (
                    flow.flow_subtype == RealEstateFlowSubtype.LOAN
                    and flow.linked_loan_hash
                ):
                    hashes.append(flow.linked_loan_hash)

        if not hashes:
            return

        loans_by_hash = await self._position_port.get_loans_by_hash(list(set(hashes)))

        for entry in entries:
            for flow in entry.flows:
                if (
                    flow.flow_subtype == RealEstateFlowSubtype.LOAN
                    and flow.linked_loan_hash
                ):
                    loan = loans_by_hash.get(flow.linked_loan_hash)
                    if loan:
                        if flow.periodic_flow:
                            flow.periodic_flow.amount = loan.current_installment
                            flow.periodic_flow.currency = loan.currency
                            flow.periodic_flow.frequency = INSTALLMENT_TO_FLOW_FREQ.get(
                                loan.installment_frequency, FlowFrequency.MONTHLY
                            )
                            flow.periodic_flow.since = loan.creation
                            flow.periodic_flow.until = loan.maturity
                        flow.payload = LoanPayload(
                            type=loan.type,
                            loan_amount=loan.loan_amount,
                            interest_rate=loan.interest_rate,
                            euribor_rate=loan.euribor_rate,
                            interest_type=loan.interest_type,
                            fixed_years=loan.fixed_years,
                            fixed_interest_rate=loan.fixed_interest_rate,
                            principal_outstanding=loan.principal_outstanding,
                            monthly_interests=loan.installment_interests,
                        )
