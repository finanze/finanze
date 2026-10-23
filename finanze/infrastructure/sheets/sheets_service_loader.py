import asyncio
import base64
import logging
import secrets
import time
from threading import Lock
from typing import Optional

from application.ports.sheets_initiator import SheetsInitiator
from domain.exception.exceptions import (
    ExternalIntegrationRequired,
    IntegrationSetupError,
    IntegrationSetupErrorCode,
)
from domain.external_integration import (
    CompleteExternalIntegrationConnectionRequest,
    ExternalIntegrationId,
    ExternalIntegrationPayload,
)
from domain.user import User
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from oauthlib.oauth2.rfc6749.errors import (
    InvalidClientError,
    InvalidGrantError,
    UnauthorizedClientError,
)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

TOKEN_FILENAME = "token.json"

AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
TOKEN_URI = "https://oauth2.googleapis.com/token"
RELAY_REDIRECT_URI = "https://finanze.me/oauth/v1/integration/callback/"
DEFAULT_COMPLETION_URL = (
    "finanze://integration/complete?integration_oauth="
    + ExternalIntegrationId.GOOGLE_SHEETS.value
)
PENDING_AUTHORIZATION_TTL_SECONDS = 15 * 60


def _client_config(credentials: ExternalIntegrationPayload) -> dict:
    client_id, client_secret = (
        credentials.get("client_id"),
        credentials.get("client_secret"),
    )
    if not client_id or not client_secret:
        raise IntegrationSetupError(IntegrationSetupErrorCode.INVALID_CREDENTIALS)

    return {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": AUTH_URI,
            "token_uri": TOKEN_URI,
            "redirect_uris": [RELAY_REDIRECT_URI],
        }
    }


def _build_state(completion_url: str) -> str:
    encoded = (
        base64.urlsafe_b64encode(completion_url.encode("utf-8"))
        .decode("ascii")
        .rstrip("=")
    )
    return f"{secrets.token_urlsafe(24)}~{encoded}"


class SheetsServiceLoader(SheetsInitiator):
    def __init__(self):
        self._base_path = None
        self._service = None
        self._service_key = None
        self._pending: dict[str, tuple[Flow, float]] = {}
        self._lock = Lock()
        self._log = logging.getLogger(__name__)

    def disconnect(self):
        self._log.debug("Disconnecting loader")
        self._base_path = None
        self._clear()

    def connect(self, user: User):
        self._log.debug("Connecting loader")
        self._base_path = user.path

    async def teardown(self):
        self._clear()
        if self._base_path:
            (self._base_path / TOKEN_FILENAME).unlink(missing_ok=True)

    def _clear(self):
        with self._lock:
            self._service = None
            self._service_key = None
            self._pending.clear()

    async def start_authorization(
        self, payload: ExternalIntegrationPayload, completion_url: Optional[str]
    ) -> str:
        flow = Flow.from_client_config(
            _client_config(payload), SCOPES, redirect_uri=RELAY_REDIRECT_URI
        )
        state = _build_state(completion_url or DEFAULT_COMPLETION_URL)
        link, _ = flow.authorization_url(
            state=state, access_type="offline", prompt="consent"
        )

        now = time.monotonic()
        with self._lock:
            self._pending = {
                key: pending
                for key, pending in self._pending.items()
                if pending[1] > now
            }
            self._pending[state] = (flow, now + PENDING_AUTHORIZATION_TTL_SECONDS)

        return link

    async def complete_authorization(
        self, request: CompleteExternalIntegrationConnectionRequest
    ) -> ExternalIntegrationPayload:
        with self._lock:
            pending = self._pending.pop(request.state, None)

        if pending is None or pending[1] <= time.monotonic():
            raise IntegrationSetupError(IntegrationSetupErrorCode.AUTHORIZATION_EXPIRED)

        if request.error:
            self._log.warning(f"Google authorization failed: {request.error}")
            if request.error == "access_denied":
                raise IntegrationSetupError(
                    IntegrationSetupErrorCode.AUTHORIZATION_DENIED
                )
            raise IntegrationSetupError(IntegrationSetupErrorCode.UNKNOWN)

        if not request.code:
            raise IntegrationSetupError(IntegrationSetupErrorCode.UNKNOWN)

        flow = pending[0]
        try:
            token = await asyncio.to_thread(flow.fetch_token, code=request.code)
        except (InvalidClientError, UnauthorizedClientError) as e:
            raise IntegrationSetupError(
                IntegrationSetupErrorCode.INVALID_CREDENTIALS
            ) from e
        except InvalidGrantError as e:
            raise IntegrationSetupError(
                IntegrationSetupErrorCode.AUTHORIZATION_EXPIRED
            ) from e
        except Warning as e:
            # oauthlib raises a Warning when the granted scopes differ from the requested ones
            raise IntegrationSetupError(
                IntegrationSetupErrorCode.AUTHORIZATION_DENIED
            ) from e

        granted_scopes = token.get("scope")
        if granted_scopes is not None and SCOPES[0] not in granted_scopes:
            raise IntegrationSetupError(IntegrationSetupErrorCode.AUTHORIZATION_DENIED)

        refresh_token = token.get("refresh_token")
        if not refresh_token:
            raise IntegrationSetupError(IntegrationSetupErrorCode.UNKNOWN)

        with self._lock:
            self._service = None
            self._service_key = None

        return {
            "client_id": flow.client_config["client_id"],
            "client_secret": flow.client_config["client_secret"],
            "refresh_token": refresh_token,
        }

    def _load_legacy_credentials(self) -> Optional[Credentials]:
        if not self._base_path:
            return None

        token_path = self._base_path / TOKEN_FILENAME
        if not token_path.is_file():
            return None

        try:
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        except ValueError:
            self._log.warning("Invalid legacy Google Sheets token file")
            return None

        if not creds.valid and not creds.refresh_token:
            return None

        return creds

    def _load_credentials(self, credentials: ExternalIntegrationPayload):
        refresh_token = credentials.get("refresh_token")
        if refresh_token:
            return Credentials(
                None,
                refresh_token=refresh_token,
                token_uri=TOKEN_URI,
                client_id=credentials.get("client_id"),
                client_secret=credentials.get("client_secret"),
                scopes=SCOPES,
            )

        creds = self._load_legacy_credentials()
        if creds is None:
            raise ExternalIntegrationRequired([ExternalIntegrationId.GOOGLE_SHEETS])

        return creds

    def service(self, credentials: ExternalIntegrationPayload):
        key = (
            credentials.get("client_id"),
            credentials.get("client_secret"),
            credentials.get("refresh_token"),
        )
        with self._lock:
            if self._service is None or self._service_key != key:
                creds = self._load_credentials(credentials)
                service = build("sheets", "v4", credentials=creds)
                self._service = service.spreadsheets()
                self._service_key = key

            return self._service
