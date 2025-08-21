from io import IOBase
from typing import IO

from pydantic import ConfigDict
from pydantic.dataclasses import dataclass


@dataclass(config=ConfigDict(arbitrary_types_allowed=True))
class FileUpload:
    filename: str
    content_type: str
    content_length: int
    data: IO[bytes] | IOBase

    def __repr__(self):
        return f"FileUpload(file_name={self.filename}, content_type={self.content_type}, content_length={self.content_length})"

    def __str__(self):
        return f"File: {self.filename}, Content-Type: {self.content_type}, Size: {self.content_length} bytes"
