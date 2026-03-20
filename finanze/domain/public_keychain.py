import base64
import hashlib
from datetime import datetime
from functools import lru_cache
from typing import Optional


def _algo1_decode(encoded_text):
    padding_needed = 4 - (len(encoded_text) % 4)
    if padding_needed != 4:
        encoded_text += "=" * padding_needed

    data = bytearray(base64.urlsafe_b64decode(encoded_text))

    k = data[0]
    payload = data[1:]

    for i in range(len(payload)):
        payload[i] ^= k

    original_bytes = payload.split(b"\x00")[0]

    return original_bytes.decode("utf-8")


class PublicKeyEntry:
    def __init__(
        self, key: str, value: str, algo: int, version: int, updated_at: datetime
    ):
        self.key = key
        self.value = value
        self.algo = algo
        self.version = version
        self.updated_at = updated_at
        self._decoded: Optional[str] = None

    def decode(self) -> str:
        if self._decoded is not None:
            return self._decoded

        if self.algo == 1:
            self._decoded = _algo1_decode(self.value)
        else:
            raise ValueError(f"Unsupported algo: {self.algo}")

        return self._decoded


class PublicKeychain:
    def __init__(self, raw_content: dict[str, PublicKeyEntry]):
        self._storage: dict[str, PublicKeyEntry] = raw_content

    @lru_cache(maxsize=256)
    def _key_hash(self, key_name: str) -> str:
        return hashlib.shake_128(key_name.encode("utf-8")).hexdigest(8)

    def get(self, key: str) -> Optional[PublicKeyEntry]:
        hashed = self._key_hash(key)
        return self._storage.get(hashed)
