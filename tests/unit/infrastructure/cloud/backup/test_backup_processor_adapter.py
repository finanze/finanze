import pytest

from domain.backup import BackupFileType, BackupProcessRequest, BackupProcessResult
from domain.exception.exceptions import (
    UnsupportedBackupProtocol,
    InvalidBackupCredentials,
)
from infrastructure.cloud.backup.backup_processor_adapter import (
    BackupProcessorAdapter,
    BackupProcessorV1,
)

PASSWORD = "test-password-123"
PAYLOAD = b"Hello World! This is a test payload for backup processing."


def _adapter():
    return BackupProcessorAdapter()


def _v1():
    return BackupProcessorV1()


def _request(payload=PAYLOAD, password=PASSWORD, protocol=1):
    return BackupProcessRequest(
        protocol=protocol,
        password=password,
        type=BackupFileType.DATA,
        payload=payload,
    )


class TestBackupProcessorAdapter:
    @pytest.mark.asyncio
    async def test_compile_delegates_to_v1(self):
        adapter = _adapter()
        result = await adapter.compile(_request())
        assert isinstance(result, BackupProcessResult)
        assert result.size > 0

    @pytest.mark.asyncio
    async def test_decompile_delegates_to_v1(self):
        adapter = _adapter()
        compiled = await adapter.compile(_request())
        decompile_req = _request(payload=compiled.payload)
        result = await adapter.decompile(decompile_req)
        assert result.payload == PAYLOAD

    @pytest.mark.asyncio
    async def test_compile_raises_on_unsupported_protocol(self):
        adapter = _adapter()
        with pytest.raises(UnsupportedBackupProtocol):
            await adapter.compile(_request(protocol=99))

    @pytest.mark.asyncio
    async def test_decompile_raises_on_unsupported_protocol(self):
        adapter = _adapter()
        with pytest.raises(UnsupportedBackupProtocol):
            await adapter.decompile(_request(protocol=99))


class TestBackupProcessorV1Compile:
    def test_returns_encrypted_compressed_payload(self):
        v1 = _v1()
        result = v1.compile(_request())
        assert isinstance(result, BackupProcessResult)
        assert result.payload != PAYLOAD
        assert result.size == len(result.payload)
        assert result.size > 0

    def test_different_passwords_produce_different_output(self):
        v1 = _v1()
        result_a = v1.compile(_request(password="password-a"))
        result_b = v1.compile(_request(password="password-b"))
        assert result_a.payload != result_b.payload

    def test_output_is_bytes(self):
        v1 = _v1()
        result = v1.compile(_request())
        assert isinstance(result.payload, bytes)


class TestBackupProcessorV1Decompile:
    def test_roundtrip_produces_original_payload(self):
        v1 = _v1()
        compiled = v1.compile(_request())
        decompile_req = _request(payload=compiled.payload)
        result = v1.decompile(decompile_req)
        assert result.payload == PAYLOAD

    def test_roundtrip_with_large_payload(self):
        v1 = _v1()
        large_payload = b"x" * 100_000
        req = _request(payload=large_payload)
        compiled = v1.compile(req)
        assert compiled.size < len(large_payload)
        decompile_req = _request(payload=compiled.payload)
        result = v1.decompile(decompile_req)
        assert result.payload == large_payload

    def test_wrong_password_raises_invalid_backup_credentials(self):
        v1 = _v1()
        compiled = v1.compile(_request(password="correct-password"))
        decompile_req = _request(payload=compiled.payload, password="wrong-password")
        with pytest.raises(InvalidBackupCredentials):
            v1.decompile(decompile_req)

    def test_corrupted_payload_raises_invalid_backup_credentials(self):
        v1 = _v1()
        with pytest.raises(InvalidBackupCredentials):
            v1.decompile(_request(payload=b"not-valid-encrypted-data"))

    def test_empty_payload_roundtrip(self):
        v1 = _v1()
        req = _request(payload=b"")
        compiled = v1.compile(req)
        assert compiled.size > 0
        decompile_req = _request(payload=compiled.payload)
        result = v1.decompile(decompile_req)
        assert result.payload == b""

    def test_binary_payload_roundtrip(self):
        v1 = _v1()
        binary_payload = bytes(range(256)) * 10
        req = _request(payload=binary_payload)
        compiled = v1.compile(req)
        decompile_req = _request(payload=compiled.payload)
        result = v1.decompile(decompile_req)
        assert result.payload == binary_payload


class TestBackupProcessorV1Key:
    def test_same_password_produces_same_key(self):
        key_a = BackupProcessorV1._key.__wrapped__("same-password")
        key_b = BackupProcessorV1._key.__wrapped__("same-password")
        assert key_a == key_b

    def test_different_passwords_produce_different_keys(self):
        key_a = BackupProcessorV1._key.__wrapped__("password-one")
        key_b = BackupProcessorV1._key.__wrapped__("password-two")
        assert key_a != key_b

    def test_key_is_valid_fernet_key_length(self):
        import base64

        key = BackupProcessorV1._key.__wrapped__("any-password")
        decoded = base64.urlsafe_b64decode(key)
        assert len(decoded) == 32
