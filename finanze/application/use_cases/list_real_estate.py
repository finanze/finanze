from application.ports.real_estate_port import RealEstatePort
from application.use_cases.get_periodic_flows import get_next_date
from domain.real_estate import RealEstate
from domain.use_cases.list_real_estate import ListRealEstate


class ListRealEstateImpl(ListRealEstate):
    def __init__(self, real_estate_port: RealEstatePort):
        self._real_estate_port = real_estate_port

    def execute(self) -> list[RealEstate]:
        entries = self._real_estate_port.get_all()

        for entry in entries:
            for flow in entry.flows:
                if flow.periodic_flow:
                    flow.periodic_flow.next_date = get_next_date(flow.periodic_flow)

        return entries
