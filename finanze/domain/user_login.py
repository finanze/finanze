from pydantic.dataclasses import dataclass


@dataclass
class LoginRequest:
    password: str
