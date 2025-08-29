from application.mixins.atomic_use_case import AtomicUCMixin
from application.ports.file_storage_port import FileStoragePort
from application.ports.periodic_flow_port import PeriodicFlowPort
from application.ports.real_estate_port import RealEstatePort
from application.ports.transaction_handler_port import TransactionHandlerPort
from domain.exception.exceptions import FlowNotFound, RealEstateNotFound
from domain.real_estate import UpdateRealEstateRequest
from domain.use_cases.update_real_estate import UpdateRealEstate


class UpdateRealEstateImpl(AtomicUCMixin, UpdateRealEstate):
    def __init__(
        self,
        real_estate_port: RealEstatePort,
        periodic_flow_port: PeriodicFlowPort,
        transaction_handler_port: TransactionHandlerPort,
        file_storage_port: FileStoragePort,
    ):
        AtomicUCMixin.__init__(self, transaction_handler_port)

        self._real_estate_port = real_estate_port
        self._periodic_flow_port = periodic_flow_port
        self._file_storage_port = file_storage_port

    async def execute(self, request: UpdateRealEstateRequest):
        real_estate = request.real_estate

        existing_real_estate = self._real_estate_port.get_by_id(real_estate.id)
        if existing_real_estate is None:
            raise RealEstateNotFound(
                f"Real estate with ID {real_estate.id} does not exist."
            )

        if request.remove_unassigned_flows:
            assigned_flows = {flow.periodic_flow_id for flow in real_estate.flows}
            for existing_flow in existing_real_estate.flows:
                if existing_flow.periodic_flow_id not in assigned_flows:
                    self._periodic_flow_port.delete(existing_flow.periodic_flow_id)

        for re_flow in real_estate.flows:
            if re_flow.periodic_flow_id is None and re_flow.periodic_flow is not None:
                re_flow.periodic_flow_id = self._periodic_flow_port.save(
                    re_flow.periodic_flow
                ).id
            elif re_flow.periodic_flow is not None:
                existing_pending_flow = self._periodic_flow_port.get_by_id(
                    re_flow.periodic_flow.id
                )
                if existing_pending_flow is None:
                    raise FlowNotFound(
                        f"Periodic flow with ID {re_flow.periodic_flow.id} does not exist."
                    )
                self._periodic_flow_port.update(re_flow.periodic_flow)

        if request.photo and request.photo.filename:
            try:
                old_photo_url = existing_real_estate.basic_info.photo_url
                if old_photo_url:
                    self._file_storage_port.delete_by_url(old_photo_url)

                photo_path = self._file_storage_port.save(request.photo, "real_estate")
                photo_url = self._file_storage_port.get_url(photo_path)
                real_estate.basic_info.photo_url = photo_url
            except ValueError as e:
                raise ValueError(f"Error uploading image: {str(e)}")
        else:
            real_estate.basic_info.photo_url = existing_real_estate.basic_info.photo_url

        try:
            real_estate.currency = existing_real_estate.currency
            if real_estate.rental_data is None:
                real_estate.rental_data = existing_real_estate.rental_data

            self._real_estate_port.update(real_estate)
        except:
            if request.photo and request.photo.filename:
                if real_estate.basic_info.photo_url:
                    self._file_storage_port.delete_by_url(
                        real_estate.basic_info.photo_url
                    )
            raise
