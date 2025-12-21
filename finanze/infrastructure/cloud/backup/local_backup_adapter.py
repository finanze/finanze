import json
from datetime import datetime
from pathlib import Path
from uuid import UUID

from application.ports.backup_repository import BackupRepository
from domain.backup import (
    BackupPieces,
    BackupTransferPiece,
    BackupDownloadParams,
    BackupsInfo,
    BackupInfo,
    BackupFileType,
    BackupUploadParams,
    BackupInfoParams,
)


class LocalBackupAdapter(BackupRepository):
    def __init__(self, storage_path: str = ".storage/backups"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def upload(self, request: BackupUploadParams) -> BackupPieces:
        uploaded_pieces = []

        for piece in request.pieces.pieces:
            try:
                pattern = f"{piece.type.value}_*"
                existing_metadata_files = list(
                    self.storage_path.glob(f"{pattern}_metadata.json")
                )
                existing_payload_files = list(
                    self.storage_path.glob(f"{pattern}_payload.bak")
                )

                for existing_file in existing_metadata_files + existing_payload_files:
                    existing_file.unlink()

                metadata = {
                    "id": str(piece.id),
                    "protocol": piece.protocol,
                    "date": piece.date.isoformat(),
                    "type": piece.type.value,
                }

                file_prefix = f"{piece.type.value}_{piece.id}"
                metadata_file = self.storage_path / f"{file_prefix}_metadata.json"
                payload_file = self.storage_path / f"{file_prefix}_payload.bak"

                with open(metadata_file, "w") as f:
                    json.dump(metadata, f, indent=2)

                with open(payload_file, "wb") as f:
                    f.write(piece.payload)

                uploaded_pieces.append(piece)
            except Exception as e:
                print(f"Error uploading backup piece {piece.type.value}: {e}")
                continue

        return BackupPieces(pieces=uploaded_pieces)

    def download(self, request: BackupDownloadParams) -> BackupPieces:
        pieces = []

        for backup_type in request.types:
            pattern = f"{backup_type.value}_*_metadata.json"
            metadata_files = list(self.storage_path.glob(pattern))

            if metadata_files:
                latest_metadata_file = max(
                    metadata_files, key=lambda p: p.stat().st_mtime
                )

                with open(latest_metadata_file, "r") as f:
                    metadata = json.load(f)

                file_prefix = f"{metadata['type']}_{metadata['id']}"
                payload_file = self.storage_path / f"{file_prefix}_payload.bak"

                with open(payload_file, "rb") as f:
                    payload = f.read()

                piece = BackupTransferPiece(
                    id=UUID(metadata["id"]),
                    protocol=metadata["protocol"],
                    date=datetime.fromisoformat(metadata["date"]),
                    type=BackupFileType(metadata["type"]),
                    payload=payload,
                )
                pieces.append(piece)

        return BackupPieces(pieces=pieces)

    def get_info(self, request: BackupInfoParams) -> BackupsInfo:
        backup_infos = {}
        metadata_files = list(self.storage_path.glob("*_metadata.json"))

        for metadata_file in metadata_files:
            with open(metadata_file, "r") as f:
                metadata = json.load(f)

            file_prefix = f"{metadata['type']}_{metadata['id']}"
            payload_file = self.storage_path / f"{file_prefix}_payload.bak"

            if payload_file.exists():
                size = payload_file.stat().st_size
                backup_type = BackupFileType(metadata["type"])
                backup_info = BackupInfo(
                    id=UUID(metadata["id"]),
                    protocol=metadata["protocol"],
                    date=datetime.fromisoformat(metadata["date"]),
                    type=backup_type,
                    size=size,
                )
                backup_infos[backup_type] = backup_info

        return BackupsInfo(pieces=backup_infos)
