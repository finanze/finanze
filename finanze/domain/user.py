import base64
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import UUID

from pydantic.dataclasses import dataclass


@dataclass
class User:
    id: UUID
    username: str
    path: Path
    last_login: Optional[datetime]

    def hashed_id(self) -> str:
        hash_bytes = hashlib.sha1(self.id.bytes).digest()[:10]
        return (
            base64.urlsafe_b64encode(hash_bytes)
            .rstrip(b"=")
            .decode("utf-8")
            .replace("-", "a")
            .replace("_", "z")
        )


@dataclass
class UserRegistration:
    id: UUID
    username: str
