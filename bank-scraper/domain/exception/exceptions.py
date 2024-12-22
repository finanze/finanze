from typing import List


class MissingFieldsError(Exception):

    def __init__(self, missing_fields: List[str]):
        self.missing_fields = missing_fields
        message = f"Missing required fields: {', '.join(missing_fields)}"
        super().__init__(message)
