from pathlib import Path
from threading import Lock

from domain.settings import GoogleCredentials
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


TOKEN_FILENAME = "token.json"


class SheetsServiceLoader:
    def __init__(self, base_path: str):
        self._base_path = Path(base_path)
        self._service = None
        self._lock = Lock()

    def _load_creds(self, credentials: GoogleCredentials):
        token_path = self._base_path / TOKEN_FILENAME

        creds = None
        if token_path.is_file():
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                client_config = self._client_config(credentials)

                flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
                creds = flow.run_local_server(port=0)

            with open(token_path, "w") as token:
                token.write(creds.to_json())

        return creds

    def _client_config(self, credentials: GoogleCredentials) -> dict:
        client_id, client_secret = credentials.client_id, credentials.client_secret
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

    def service(self, credentials: GoogleCredentials):
        with self._lock:
            if not self._service:
                creds = self._load_creds(credentials)
                service = build("sheets", "v4", credentials=creds)
                self._service = service.spreadsheets()

            return self._service
