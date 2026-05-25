from typing import Optional

from pydantic.dataclasses import dataclass


@dataclass
class LoginRequest:
    username: str
    password: Optional[str] = None
    guest: bool = False


@dataclass
class ChangePasswordRequest:
    username: str
    old_password: str
    new_password: str
