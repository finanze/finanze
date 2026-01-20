import logging

from domain.backup import BackupFileType
from domain.exception.exceptions import TooManyRequests
from infrastructure.client.cloud.backup.file_transfer_strategy import (
    FileTransferStrategy,
)
from infrastructure.client.http.http_session import get_http_session


class HttpFileTransferStrategy(FileTransferStrategy):
    TIMEOUT = 60

    def __init__(self):
        self._log = logging.getLogger(__name__)
        self._session = get_http_session()

    async def upload(
        self,
        url: str,
        method: str,
        payload: bytes,
        headers: dict[str, str],
        backup_type: BackupFileType,
    ) -> None:
        upload_headers = headers.copy()
        upload_headers["Content-Length"] = str(len(payload))
        self._log.info(f"Uploading backup piece: {upload_headers}")

        upload_response = await self._session.request(
            method=method,
            url=url,
            data=payload,
            headers=upload_headers,
            timeout=self.TIMEOUT,
        )

        if upload_response.status == 429:
            raise TooManyRequests()

        upload_response.raise_for_status()

    async def download(self, url: str, backup_type: BackupFileType) -> bytes:
        payload_response = await self._session.get(
            url,
            timeout=self.TIMEOUT,
        )

        if payload_response.status == 429:
            raise TooManyRequests()

        payload_response.raise_for_status()
        return await payload_response.read()
