from enum import Enum

from pydantic.dataclasses import dataclass


class ExportTarget(str, Enum):
    GOOGLE_SHEETS = "GOOGLE_SHEETS"


@dataclass
class ExportRequest:
    target: ExportTarget
