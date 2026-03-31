from application.ports.position_port import PositionPort
from application.ports.real_estate_port import RealEstatePort
from application.use_cases.get_periodic_flows import get_next_date
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
                    and isinstance(flow.payload, LoanPayload)
                    and flow.payload.linked_loan_hash
                ):
                    hashes.append(flow.payload.linked_loan_hash)

        if not hashes:
            return

        loans_by_hash = await self._position_port.get_loans_by_hash(hashes)

        for entry in entries:
            for flow in entry.flows:
                if (
                    flow.flow_subtype == RealEstateFlowSubtype.LOAN
                    and isinstance(flow.payload, LoanPayload)
                    and flow.payload.linked_loan_hash
                ):
                    loan = loans_by_hash.get(flow.payload.linked_loan_hash)
                    if loan:
                        flow.payload.type = loan.type
                        flow.payload.loan_amount = loan.loan_amount
                        flow.payload.interest_rate = loan.interest_rate
                        flow.payload.euribor_rate = loan.euribor_rate
                        flow.payload.interest_type = loan.interest_type
                        flow.payload.fixed_years = loan.fixed_years
                        flow.payload.fixed_interest_rate = loan.fixed_interest_rate
                        flow.payload.principal_outstanding = loan.principal_outstanding
                        flow.payload.monthly_interests = loan.installment_interests
