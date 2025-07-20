from pydantic.dataclasses import dataclass


@dataclass
class LoginRequest:
    username: str
    password: str


@dataclass
class ChangePasswordRequest:
    username: str
    old_password: str
    new_password: str
