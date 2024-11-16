import abc
from typing import Optional

from domain.scrap_result import ScrapResult


class BankScraper(metaclass=abc.ABCMeta):
    def login(self, credentials: tuple, params: dict) -> Optional[dict]:
        raise NotImplementedError

    async def generate(self) -> ScrapResult:
        raise NotImplementedError
