from application.ports.external_integration_port import ExternalIntegrationPort
from application.ports.external_tx_labeling_provider import (
    ExternalTxLabelingProvider,
)
from domain.exception.exceptions import IntegrationNotFound
from domain.external_integration import ExternalIntegrationId
from domain.external_labeling import (
    ExternalLabelingModelValidation,
    ValidateExternalLabelingModelRequest,
)
from domain.use_cases.validate_external_labeling_model import (
    ValidateExternalLabelingModel,
)

MAX_MODEL_ID_LENGTH = 200


class ValidateExternalLabelingModelImpl(ValidateExternalLabelingModel):
    def __init__(
        self,
        external_integration_port: ExternalIntegrationPort,
        providers: dict[ExternalIntegrationId, ExternalTxLabelingProvider],
    ):
        self._external_integration_port = external_integration_port
        self._providers = providers

    async def execute(
        self, request: ValidateExternalLabelingModelRequest
    ) -> ExternalLabelingModelValidation:
        provider = self._providers.get(request.provider)
        if provider is None:
            raise IntegrationNotFound()

        model_id = (request.model or "").strip()
        if not model_id or len(model_id) > MAX_MODEL_ID_LENGTH:
            return ExternalLabelingModelValidation(valid=False)

        upstream_provider = (request.upstream_provider or "").strip() or None
        if upstream_provider and (
            not provider.supports_upstream_providers()
            or len(upstream_provider) > MAX_MODEL_ID_LENGTH
        ):
            return ExternalLabelingModelValidation(valid=False)

        credentials = await self._external_integration_port.get_payload(
            request.provider
        )
        model = await provider.get_model(model_id, credentials, upstream_provider)
        return ExternalLabelingModelValidation(valid=model is not None, model=model)
