from __future__ import annotations

import logging
from typing import Optional

from application.ports.instrument_info_provider import InstrumentInfoProvider
from domain.dezimal import Dezimal
from domain.instrument import (
    InstrumentDataRequest,
    InstrumentInfo,
    InstrumentOverview,
    InstrumentType,
)
from infrastructure.client.instrument.ft_client import FtClient
from infrastructure.client.instrument.yfinance_client import YFinanceClient


class InstrumentProviderAdapter(InstrumentInfoProvider):
    def __init__(self):
        self._ft = FtClient()
        self._yf = YFinanceClient()
        # self._finect = FinectClient()
        self._log = logging.getLogger(__name__)

    def lookup(self, request: InstrumentDataRequest) -> list[InstrumentOverview]:
        query = request.isin or request.ticker or request.name
        if not query:
            return []

        if request.type == InstrumentType.STOCK:
            results = self._yf.lookup(request)
        else:
            results = self._ft.search(request)

        return [self._normalize_overview(o) for o in results]

    def get_info(self, request: InstrumentDataRequest) -> Optional[InstrumentInfo]:
        query = request.ticker or request.isin or request.name
        if not query:
            return None

        info = self._yf.get_instrument_info(query, request.type)
        if info is None:
            return None

        return self._normalize_info(info)

    @staticmethod
    def _is_gbp_pence_currency(currency: Optional[str]) -> bool:
        if not currency:
            return False
        c = currency.strip()
        if len(c) < 3:
            return False
        if c[:2].upper() != "GB":
            return False
        last = c[-1]
        if last in ("p", "P"):
            return True
        if last.upper() == "X":
            return True
        return False

    def _normalize_overview(self, overview: InstrumentOverview) -> InstrumentOverview:
        if overview.currency and self._is_gbp_pence_currency(overview.currency):
            overview.currency = "GBP"
            if overview.price is not None:
                overview.price = Dezimal(overview.price) / Dezimal(100)
        return overview

    def _normalize_info(self, info: InstrumentInfo) -> InstrumentInfo:
        if info.currency and self._is_gbp_pence_currency(info.currency):
            info.currency = "GBP"
            if info.price is not None:
                info.price = Dezimal(info.price) / Dezimal(100)
        return info
