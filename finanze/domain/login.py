from enum import Enum
from typing import Optional

from pydantic.dataclasses import dataclass


class LoginStatusCode(str, Enum):
    LOCKED = "LOCKED"
    UNLOCKED = "UNLOCKED"


@dataclass
class LoginStatus:
    status: LoginStatusCode
    user: Optional[str] = None
    last_logged: Optional[str] = None
