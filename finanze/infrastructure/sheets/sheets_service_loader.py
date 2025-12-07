import logging
from threading import Lock

from application.ports.sheets_initiator import SheetsInitiator
from domain.external_integration import (
    ExternalIntegrationPayload,
)
from domain.user import User
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


TOKEN_FILENAME = "token.json"


def _client_config(credentials: ExternalIntegrationPayload) -> dict:
    client_id, client_secret = (
        credentials.get("client_id"),
        credentials.get("client_secret"),
    )
    if not client_id or not client_secret:
        raise ValueError("Google credentials not found")

    return {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }


class SheetsServiceLoader(SheetsInitiator):
    def __init__(self):
        self._base_path = None
        self._service = None
        self._lock = Lock()
        self._log = logging.getLogger(__name__)

    def disconnect(self):
        self._log.debug("Disconnecting loader")
        self._base_path = None

    def connect(self, user: User):
        self._log.debug("Connecting loader")
        self._base_path = user.path

    def setup(self, credentials: ExternalIntegrationPayload):
        if not self._base_path:
            raise ValueError("Base path not set")

        token_path = self._base_path / TOKEN_FILENAME

        client_config = _client_config(credentials)

        flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
        creds = flow.run_local_server(port=0, timeout_seconds=180)

        with open(token_path, "w") as token:
            token.write(creds.to_json())

        return creds

    def _load_credentials(self, credentials: ExternalIntegrationPayload):
        if not self._base_path:
            raise ValueError("Base path not set")

        token_path = self._base_path / TOKEN_FILENAME

        creds = None
        if token_path.is_file():
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                return self.setup(credentials)

            with open(token_path, "w") as token:
                token.write(creds.to_json())

        return creds

    def service(self, credentials: ExternalIntegrationPayload):
        with self._lock:
            if not self._service:
                creds = self._load_credentials(credentials)
                service = build("sheets", "v4", credentials=creds)
                self._service = service.spreadsheets()

            return self._service
