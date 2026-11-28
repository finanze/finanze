from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from application.ports.connectable_integration import ConnectableIntegration
from application.ports.oauth_connectable_integration import (
    OAuthConnectableIntegration,
)
from domain.external_integration import (
    ExternalIntegrationId,
    ForwardIntegrationOAuthCallbackRequest,
)
from domain.use_cases.forward_integration_oauth_callback import (
    ForwardIntegrationOAuthCallback,
)


def _with_callback_params(
    destination: str, request: ForwardIntegrationOAuthCallbackRequest
) -> str:
    parts = urlsplit(destination)
    params = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key not in ("state", "code", "error", "client_id")
    ]
    params += [
        (key, value)
        for key, value in (
            ("state", request.state),
            ("code", request.code),
            ("error", request.error),
            ("client_id", request.client_id),
        )
        if value
    ]
    return urlunsplit(parts._replace(query=urlencode(params)))


class ForwardIntegrationOAuthCallbackImpl(ForwardIntegrationOAuthCallback):
    def __init__(
        self, integrations: dict[ExternalIntegrationId, ConnectableIntegration]
    ):
        self._integrations = integrations

    async def execute(
        self, request: ForwardIntegrationOAuthCallbackRequest
    ) -> Optional[str]:
        for integration in self._integrations.values():
            if not isinstance(integration, OAuthConnectableIntegration):
                continue
            destination = await integration.callback_destination(request.state)
            if destination:
                return _with_callback_params(destination, request)
        return None
