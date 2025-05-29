from enum import Enum

from pydantic.dataclasses import dataclass


class LoginStatusCode(str, Enum):
    LOCKED = "LOCKED"
    UNLOCKED = "UNLOCKED"


@dataclass
class LoginStatus:
    status: LoginStatusCode
