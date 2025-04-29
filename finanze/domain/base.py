import inspect
from abc import ABC
from typing import TypeVar

from domain.exception.exceptions import MissingFieldsError

T = TypeVar("T", bound="BaseDataClass")


class BaseData(ABC):
    @classmethod
    def from_dict(cls: type[T], env: dict) -> T:
        parameters = inspect.signature(cls).parameters
        required_fields = {
            name for name, param in parameters.items()
            if param.default == param.empty and param.kind in (param.POSITIONAL_OR_KEYWORD, param.KEYWORD_ONLY)
        }

        missing_fields = list(required_fields - env.keys())
        if missing_fields:
            raise MissingFieldsError(missing_fields)

        return cls(**{
            k: v for k, v in env.items()
            if k in parameters
        })
