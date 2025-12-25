import logging

from application.ports.cloud_register import CloudRegister
from domain.cloud_auth import CloudAuthRequest, CloudAuthResponse
from domain.use_cases.handle_cloud_auth import HandleCloudAuth


class HandleCloudAuthImpl(HandleCloudAuth):
    def __init__(
        self,
        cloud_register: CloudRegister,
    ):
        self._cloud_register = cloud_register
        self._log = logging.getLogger(__name__)

    def execute(self, request: CloudAuthRequest) -> CloudAuthResponse:
        if (
            not request.token
            or not request.token.access_token
            or request.token.access_token.strip() == ""
        ):
            self._log.debug("Token is null/empty, clearing auth data...")
            self._cloud_register.clear_auth()
            return CloudAuthResponse(role=None, permissions=[])

        self._log.debug(
            f"Handling cloud auth for token: {request.token.access_token[:10]}..."
        )
        token_data = self._cloud_register.decode_token(request.token.access_token)

        self._cloud_register.save_auth(request.token)

        self._log.info(
            f"Cloud auth successful for email: {token_data.email}, role: {token_data.role}, permissions: {token_data.permissions}"
        )

        return CloudAuthResponse(
            role=token_data.role, permissions=token_data.permissions
        )
