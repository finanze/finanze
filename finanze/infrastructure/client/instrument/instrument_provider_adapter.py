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
from infrastructure.client.instrument.extraetf_client import ExtraEtfClient
from infrastructure.client.instrument.finect_client import FinectClient
from infrastructure.client.instrument.ft_client import FtClient
from infrastructure.client.instrument.tradingview_client import TradingViewClient
from infrastructure.client.instrument.yfinance_client import YFinanceClient

MAX_INSTRUMENTS_RETURNED = 15


class InstrumentProviderAdapter(InstrumentInfoProvider):
    def __init__(self):
        self._ft = FtClient()
        self._yf = YFinanceClient()
        self._finect = FinectClient()
        self._tv = TradingViewClient()
        self._ee = ExtraEtfClient()
        self._log = logging.getLogger(__name__)

    def lookup(self, request: InstrumentDataRequest) -> list[InstrumentOverview]:
        query = request.isin or request.ticker or request.name
        if not query:
            return []

        try:
            if request.type == InstrumentType.STOCK:
                results = self._stock_search(request)
            else:
                results = self._fund_etf_search(request)
        except Exception:
            self._log.exception(
                "InstrumentProviderAdapter lookup failed, returning empty list"
            )
            return []

        return [
            self._normalize_overview(overview)
            for overview in results[:MAX_INSTRUMENTS_RETURNED]
        ]

    def _stock_search(self, request: InstrumentDataRequest) -> list[InstrumentOverview]:
        try:
            return self._tv.search(request)
        except Exception:
            self._log.exception(
                "TradingViewClient search failed, falling back to YFinanceClient"
            )

        return self._yf.lookup(request)

    def _fund_etf_search(
        self, request: InstrumentDataRequest
    ) -> list[InstrumentOverview]:
        try:
            return self._finect.search(request)
        except Exception:
            self._log.exception("FinectClient search failed, falling back to FtClient")

        try:
            return self._ft.search(request)
        except Exception:
            self._log.exception(
                "FinectClient search failed, falling back to YFinanceClient"
            )

        if request.type == InstrumentType.ETF:
            try:
                return self._ee.search(request)
            except Exception:
                self._log.exception(
                    "ExtraEtfClient search failed, falling back to FinectClient"
                )

        return self._yf.lookup(request)

    def get_info(self, request: InstrumentDataRequest) -> Optional[InstrumentInfo]:
        query = request.ticker or request.isin or request.name
        if not query:
            return None

        try:
            if request.type != InstrumentType.STOCK:
                info = self._get_instrument_info(query, request.type)
            else:
                info = self._yf.get_instrument_info(query, request.type)
        except Exception:
            self._log.exception(
                "InstrumentProviderAdapter get_info failed, returning None"
            )
            return None

        if info is None:
            return None

        return self._normalize_info(info)

    def _get_instrument_info(
        self, query: str, instrument_type: InstrumentType
    ) -> Optional[InstrumentInfo]:
        try:
            info = self._finect.get_instrument_info(query, instrument_type)
            if info:
                return info
            else:
                self._log.warning(
                    "FinectClient returned no info, falling back to Yfinance"
                )
        except Exception:
            self._log.exception(
                "FinectClient get_instrument_info failed, falling back to Yfinance"
            )
        return self._yf.get_instrument_info(query, instrument_type)

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
