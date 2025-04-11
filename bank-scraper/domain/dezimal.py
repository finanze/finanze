from decimal import Decimal, InvalidOperation
from typing import Union, Any

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema
from typing_extensions import Self

ValidDezimal = Union[int, float, Decimal, str, 'Dezimal']
ValidDezimalOperand = Union[int, Decimal, 'Dezimal']


class Dezimal:
    val: Decimal

    def __init__(self, value: ValidDezimal):
        try:
            if isinstance(value, float):
                self.val = Decimal(str(value))

            elif isinstance(value, (Decimal, int, str)):
                self.val = Decimal(value)

            elif isinstance(value, Dezimal):
                self.val = value.val

            else:
                raise ValueError(f'Invalid type {type(value)}')

        except InvalidOperation as e:
            raise ValueError(
                'Expecting int, float, Decimal or a str.'
                f'Found {type(value)}.',
            ) from e

    def __str__(self) -> str:
        return f'{self.val:f}'

    def __repr__(self) -> str:
        return f'D({self.val!s})'

    def __hash__(self) -> int:
        return hash(self.val)

    def __gt__(self, other: ValidDezimalOperand) -> bool:
        other_decimal = _parse(other)
        return self.val.compare_signal(other_decimal) == Decimal(1)

    def __lt__(self, other: ValidDezimalOperand) -> bool:
        other_decimal = _parse(other)
        return self.val.compare_signal(other_decimal) == Decimal(-1)

    def __le__(self, other: ValidDezimalOperand) -> bool:
        other_decimal = _parse(other)
        return self.val.compare_signal(other_decimal) in (Decimal(-1), Decimal(0))

    def __ge__(self, other: ValidDezimalOperand) -> bool:
        other_decimal = _parse(other)
        return self.val.compare_signal(other_decimal) in (Decimal(1), Decimal(0))

    def __eq__(self, other: object) -> bool:
        other_decimal: ValidDezimalOperand
        if isinstance(other, Dezimal):
            other_decimal = other.val
        elif isinstance(other, int):
            other_decimal = other
        else:
            return False

        return self.val.compare_signal(other_decimal) == Decimal(0)

    def __add__(self, other: ValidDezimalOperand) -> Self:
        other_decimal = _parse(other)
        return Dezimal(self.val.__add__(other_decimal))

    def __sub__(self, other: ValidDezimalOperand) -> Self:
        other_decimal = _parse(other)
        return Dezimal(self.val.__sub__(other_decimal))

    def __mul__(self, other: ValidDezimalOperand) -> Self:
        other_decimal = _parse(other)
        return Dezimal(self.val.__mul__(other_decimal))

    def __truediv__(self, other: ValidDezimalOperand) -> Self:
        other_decimal = _parse(other)
        return Dezimal(self.val.__truediv__(other_decimal))

    def __floordiv__(self, other: ValidDezimalOperand) -> Self:
        other_decimal = _parse(other)
        return Dezimal(self.val.__floordiv__(other_decimal))

    def __pow__(self, other: ValidDezimalOperand) -> Self:
        other_decimal = _parse(other)
        return Dezimal(self.val.__pow__(other_decimal))

    def __radd__(self, other: ValidDezimalOperand) -> Self:
        other_decimal = _parse(other)
        return Dezimal(self.val.__radd__(other_decimal))

    def __rsub__(self, other: ValidDezimalOperand) -> Self:
        other_decimal = _parse(other)
        return Dezimal(self.val.__rsub__(other_decimal))

    def __rmul__(self, other: ValidDezimalOperand) -> Self:
        other_decimal = _parse(other)
        return Dezimal(self.val.__rmul__(other_decimal))

    def __rtruediv__(self, other: ValidDezimalOperand) -> Self:
        other_decimal = _parse(other)
        return Dezimal(self.val.__rtruediv__(other_decimal))

    def __rfloordiv__(self, other: ValidDezimalOperand) -> Self:
        other_decimal = _parse(other)
        return Dezimal(self.val.__rfloordiv__(other_decimal))

    def __mod__(self, other: ValidDezimalOperand) -> Self:
        other_decimal = _parse(other)
        return Dezimal(self.val.__mod__(other_decimal))

    def __rmod__(self, other: ValidDezimalOperand) -> Self:
        other_decimal = _parse(other)
        return Dezimal(self.val.__rmod__(other_decimal))

    def __round__(self, ndigits: int) -> Self:
        return Dezimal(round(self.val, ndigits))

    def __float__(self) -> float:
        return float(self.val)

    def __neg__(self) -> Self:
        return Dezimal(self.val.__neg__())

    def __abs__(self) -> Self:
        return Dezimal(self.val.copy_abs())

    @classmethod
    def __get_pydantic_core_schema__(
            cls, _source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:

        def validate(value: ValidDezimal) -> Dezimal:
            if isinstance(value, Dezimal):
                return value
            return Dezimal(value)

        return core_schema.no_info_plain_validator_function(
            validate,
            serialization=core_schema.to_string_ser_schema(),
        )


def _parse(other: ValidDezimalOperand) -> Decimal:
    if isinstance(other, Dezimal):
        return other.val
    elif isinstance(other, int):
        return Decimal(other)
    else:
        raise ValueError(f'Invalid type {type(other)}')
