from enum import Enum
from typing import Optional

from pydantic.dataclasses import dataclass


class ExportTarget(str, Enum):
    GOOGLE_SHEETS = "GOOGLE_SHEETS"


@dataclass
class ExportOptions:
    exclude_non_real: Optional[bool] = None


@dataclass
class ExportRequest:
    target: ExportTarget
    options: Optional[ExportOptions] = None
