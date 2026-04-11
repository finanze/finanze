import logging
import os
import pickle
from typing import Optional

from domain.instrument import (
    InstrumentDataRequest,
    InstrumentInfo,
    InstrumentOverview,
    InstrumentType,
)

_PKL_PATH = os.path.join(os.path.dirname(__file__), "etfs.pkl")


class LocalEtfClient:
    def __init__(self) -> None:
        self._data: Optional[dict] = None
        self._log = logging.getLogger(__name__)

    def _load(self) -> dict:
        if self._data is None:
            with open(_PKL_PATH, "rb") as f:
                self._data = pickle.load(f)
        return self._data

    async def search(self, request: InstrumentDataRequest) -> list[InstrumentOverview]:
        if request.type != InstrumentType.ETF:
            return []

        query = request.isin or request.ticker or request.name
        if not query:
            return []

        query_lower = query.strip().lower()
        if not query_lower:
            return []

        results: list[InstrumentOverview] = []
        for entry in self._load().values():
            isin = (entry.get("isin") or "").lower()
            ticker = (entry.get("ticker") or "").lower()
            name = (entry.get("name") or "").lower()

            if (
                isin.startswith(query_lower)
                or ticker.startswith(query_lower)
                or name.startswith(query_lower)
            ):
                results.append(
                    InstrumentOverview(
                        isin=entry.get("isin"),
                        name=entry.get("name"),
                        currency=entry.get("currency"),
                        symbol=entry.get("ticker"),
                        type=InstrumentType.ETF,
                        price=None,
                    )
                )

        return results

    async def get_instrument_info(
        self, query: str, instrument_type: InstrumentType
    ) -> Optional[InstrumentInfo]:
        return None
