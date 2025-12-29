import logging
from typing import Optional

from application.ports.cloud_register import CloudRegister
from domain.cloud_auth import CloudAuthData
from domain.use_cases.get_cloud_auth import GetCloudAuth


class GetCloudAuthImpl(GetCloudAuth):
    def __init__(self, cloud_register: CloudRegister):
        self._cloud_register = cloud_register
        self._log = logging.getLogger(__name__)

    def execute(self) -> Optional[CloudAuthData]:
        auth_data = self._cloud_register.get_auth()

        if auth_data is None:
            self._log.debug("No auth data")
            return None

        self._log.debug(f"Auth token found for email: {auth_data.email}")

        return auth_data
