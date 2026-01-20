import logging
import os
from datetime import datetime
from uuid import UUID

import httpx
from aiocache import cached, Cache

from application.ports.backup_repository import BackupRepository
from domain.backup import (
    BackupPieces,
    BackupDownloadParams,
    BackupsInfo,
    BackupInfo,
    BackupTransferPiece,
    BackupFileType,
    BackupUploadParams,
    BackupInfoParams,
)
from domain.cloud_auth import CloudAuthData
from domain.exception.exceptions import TooManyRequests
from infrastructure.client.cloud.backup.file_transfer_strategy import (
    FileTransferStrategy,
)
from infrastructure.client.http.http_session import get_http_session


class BackupClient(BackupRepository):
    BASE_URL = os.getenv("CLOUD_URL") or "https://api.finanze.me"
    TIMEOUT = 60

    def __init__(self, file_transfer_strategy: FileTransferStrategy):
        self._log = logging.getLogger(__name__)
        self._session = get_http_session()
        self._file_transfer_strategy = file_transfer_strategy

    def _get_auth_headers(self, auth: CloudAuthData) -> dict[str, str]:
        """Get authentication headers from auth data."""
        return {
            "Authorization": f"{auth.token.token_type} {auth.token.access_token}",
            "Content-Type": "application/json",
        }

    async def upload(self, request: BackupUploadParams) -> BackupPieces:
        """Upload backup pieces to the cloud storage."""
        if not request.pieces.pieces:
            return BackupPieces(pieces=[])

        try:
            # Step 1: Request upload URLs from the API
            upload_request_body = {
                "pieces": [
                    {
                        "id": str(piece.id),
                        "type": piece.type.value,
                        "size": piece.size,
                        "date": piece.date.isoformat(),
                        "protocol": piece.protocol,
                    }
                    for piece in request.pieces.pieces
                ]
            }

            headers = self._get_auth_headers(request.auth)
            response = await self._session.post(
                f"{self.BASE_URL}/v1/backups/upload",
                json=upload_request_body,
                headers=headers,
                timeout=self.TIMEOUT,
            )

            if response.status == 429:
                raise TooManyRequests()

            response.raise_for_status()
            upload_response = await response.json()

            # Step 2: Upload each piece to the presigned URL
            uploaded_pieces = []
            for upload_info in upload_response.get("uploads", []):
                # Find the corresponding piece
                piece = next(
                    (
                        p
                        for p in request.pieces.pieces
                        if p.type.value == upload_info["type"]
                    ),
                    None,
                )
                if not piece:
                    self._log.warning(f"No piece found for type {upload_info['type']}")
                    continue

                await self._file_transfer_strategy.upload(
                    url=upload_info["url"],
                    method=upload_info["method"],
                    payload=piece.payload,
                    headers=upload_info.get("headers", {}),
                    backup_type=piece.type,
                )

                uploaded_pieces.append(piece)
                self._log.info(
                    f"Successfully uploaded backup piece: {piece.type.value}"
                )

            return BackupPieces(pieces=uploaded_pieces)

        except (httpx.RequestError, TimeoutError) as e:
            self._log.error(f"Error uploading backup: {e}")
            raise
        except Exception as e:
            self._log.error(f"Unexpected error uploading backup: {e}")
            raise

    async def download(self, request: BackupDownloadParams) -> BackupPieces:
        """Download backup pieces from the cloud storage."""
        if not request.types:
            return BackupPieces(pieces=[])

        try:
            # Step 1: Get download URLs from the API
            params = [("type", backup_type.value) for backup_type in request.types]
            headers = self._get_auth_headers(request.auth)

            response = await self._session.get(
                f"{self.BASE_URL}/v1/backups/download",
                params=params,
                headers=headers,
                timeout=self.TIMEOUT,
            )

            if response.status == 429:
                raise TooManyRequests()

            response.raise_for_status()
            download_response = await response.json()

            # Step 2: Download each piece from the presigned URL
            pieces = []
            for backup_type_str, piece_info in download_response.get(
                "pieces", {}
            ).items():
                try:
                    download_url = piece_info.get("url")
                    if not download_url:
                        self._log.warning(
                            f"No URL found for backup type {backup_type_str}"
                        )
                        continue

                    payload = await self._file_transfer_strategy.download(
                        download_url,
                        BackupFileType(piece_info["type"]),
                    )

                    piece = BackupTransferPiece(
                        id=UUID(piece_info["id"]),
                        protocol=piece_info["protocol"],
                        date=datetime.fromisoformat(piece_info["date"]),
                        type=BackupFileType(piece_info["type"]),
                        payload=payload,
                        size=len(payload),
                    )
                    pieces.append(piece)
                    self._log.info(
                        f"Successfully downloaded backup piece: {backup_type_str}"
                    )

                except Exception as e:
                    self._log.error(f"Error downloading piece {backup_type_str}: {e}")
                    continue

            return BackupPieces(pieces=pieces)

        except (httpx.RequestError, TimeoutError) as e:
            self._log.error(f"Error downloading backup: {e}")
            raise
        except Exception as e:
            self._log.error(f"Unexpected error downloading backup: {e}")
            raise

    @cached(cache=Cache.MEMORY, ttl=1, key_builder=lambda f, self, request: "info")
    async def get_info(self, request: BackupInfoParams) -> BackupsInfo:
        """Get information about available backups in the cloud."""
        try:
            headers = self._get_auth_headers(request.auth)
            response = await self._session.get(
                f"{self.BASE_URL}/v1/backups",
                headers=headers,
                timeout=self.TIMEOUT,
            )

            if response.status == 429:
                raise TooManyRequests()

            response.raise_for_status()
            info_response = await response.json()

            backup_infos = {}
            for backup_type_str, piece_info in info_response.get("pieces", {}).items():
                try:
                    backup_type = BackupFileType(backup_type_str)
                    backup_info = BackupInfo(
                        id=UUID(piece_info["id"]),
                        protocol=piece_info["protocol"],
                        date=datetime.fromisoformat(piece_info["date"]),
                        type=backup_type,
                        size=piece_info["size"],
                    )
                    backup_infos[backup_type] = backup_info
                except (KeyError, ValueError) as e:
                    self._log.warning(
                        f"Error parsing backup info for {backup_type_str}: {e}"
                    )
                    continue

            return BackupsInfo(pieces=backup_infos)

        except (httpx.RequestError, TimeoutError) as e:
            self._log.error(f"Error getting backup info: {e}")
            raise
        except Exception as e:
            self._log.error(f"Unexpected error getting backup info: {e}")
            raise
