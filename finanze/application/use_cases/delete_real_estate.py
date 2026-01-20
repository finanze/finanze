from application.mixins.atomic_use_case import AtomicUCMixin
from application.ports.file_storage_port import FileStoragePort
from application.ports.periodic_flow_port import PeriodicFlowPort
from application.ports.real_estate_port import RealEstatePort
from application.ports.transaction_handler_port import TransactionHandlerPort
from domain.exception.exceptions import RealEstateNotFound
from domain.real_estate import DeleteRealEstateRequest
from domain.use_cases.delete_real_estate import DeleteRealEstate


class DeleteRealEstateImpl(AtomicUCMixin, DeleteRealEstate):
    def __init__(
        self,
        real_estate_repository: RealEstatePort,
        periodic_flow_port: PeriodicFlowPort,
        transaction_handler_port: TransactionHandlerPort,
        file_storage_port: FileStoragePort,
    ):
        AtomicUCMixin.__init__(self, transaction_handler_port)

        self._real_estate_repository = real_estate_repository
        self._periodic_flow_port = periodic_flow_port
        self._file_storage_port = file_storage_port

    async def execute(self, delete_request: DeleteRealEstateRequest):
        real_estate = await self._real_estate_repository.get_by_id(delete_request.id)
        if real_estate is None:
            raise RealEstateNotFound(
                f"Real estate with ID {delete_request.id} does not exist."
            )

        if delete_request.remove_related_flows:
            for flow in real_estate.flows:
                if flow.periodic_flow_id:
                    await self._periodic_flow_port.delete(flow.periodic_flow_id)

        await self._real_estate_repository.delete(delete_request.id)

        old_photo_url = real_estate.basic_info.photo_url
        if old_photo_url:
            self._file_storage_port.delete_by_url(old_photo_url)
