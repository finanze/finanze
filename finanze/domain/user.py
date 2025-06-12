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


@dataclass
class UserRegistration:
    id: UUID
    username: str
