import logging

from application.ports.datasource_initiator import DatasourceInitiator
from domain.data_init import DatasourceInitParams
from domain.use_cases.user_login import UserLogin
from domain.user_login import LoginRequest


class UserLoginImpl(UserLogin):
    def __init__(self, source_initiator: DatasourceInitiator):
        self._source_initiator = source_initiator
        self._log = logging.getLogger(__name__)

    def execute(self, login_request: LoginRequest):
        params = DatasourceInitParams(password=login_request.password)
        self._source_initiator.initialize(params)
