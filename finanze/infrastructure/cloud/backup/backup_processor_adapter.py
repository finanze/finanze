import base64
import logging
from hashlib import pbkdf2_hmac

import zlib
from cryptography.fernet import Fernet, InvalidToken

from application.ports.backup_processor import BackupProcessor
from domain.backup import BackupProcessRequest, BackupProcessResult
from domain.exception.exceptions import (
    UnsupportedBackupProtocol,
    InvalidBackupCredentials,
)


class BackupProcessorAdapter(BackupProcessor):
    def __init__(self):
        self._protocols = {1: BackupProcessorV1()}

    def compile(self, data: BackupProcessRequest) -> BackupProcessResult:
        implementation = self._protocols.get(data.protocol)
        if implementation is None:
            raise UnsupportedBackupProtocol(data.protocol)

        return implementation.compile(data)

    def decompile(self, data: BackupProcessRequest) -> BackupProcessResult:
        implementation = self._protocols.get(data.protocol)
        if implementation is None:
            raise UnsupportedBackupProtocol(data.protocol)

        return implementation.decompile(data)


class BackupProcessorV1:
    def __init__(self):
        self._log = logging.getLogger(__name__)

    def compile(self, data: BackupProcessRequest) -> BackupProcessResult:
        compressed = zlib.compress(data.payload, level=9)

        key = self._key(data.password)
        fernet = Fernet(key)
        encrypted = fernet.encrypt(compressed)
        encrypted = base64.urlsafe_b64decode(encrypted)

        return BackupProcessResult(payload=encrypted)

    def decompile(self, data: BackupProcessRequest) -> BackupProcessResult:
        key = self._key(data.password)

        try:
            fernet = Fernet(key)
            data.payload = base64.urlsafe_b64encode(data.payload)
            decrypted = fernet.decrypt(data.payload)
        except (ValueError, InvalidToken) as e:
            raise InvalidBackupCredentials from e

        decompressed = zlib.decompress(decrypted)

        return BackupProcessResult(payload=decompressed)

    @staticmethod
    def _key(password: str) -> bytes:
        key_bytes = pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            b"finanze-backup-salt",
            100000,
            dklen=32,
        )
        return base64.urlsafe_b64encode(key_bytes)
