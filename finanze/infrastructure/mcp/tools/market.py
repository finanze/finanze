from typing import Annotated, Optional

from domain.instrument import InstrumentDataRequest, InstrumentType
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from infrastructure.mcp.registry import ToolRegistry
from infrastructure.mcp.tools.common import CurrencyCode, resolve_currency
from infrastructure.mcp.use_cases import McpUseCases

InstrumentName = Annotated[Optional[str], Field(description="Name or part of it.")]
InstrumentIsin = Annotated[Optional[str], Field(description="ISIN code.")]
InstrumentTicker = Annotated[Optional[str], Field(description="Ticker symbol.")]


def _instrument_request(type, name, isin, ticker) -> InstrumentDataRequest:
    if not (name or isin or ticker):
        raise ToolError("Provide at least one of name, isin or ticker.")
    return InstrumentDataRequest(type=type, name=name, isin=isin, ticker=ticker)


def register(registry: ToolRegistry, ucs: McpUseCases):
    @registry.read("Get exchange rates")
    async def get_exchange_rates(
        base_currency: CurrencyCode = None,
        currencies: Annotated[
            Optional[list[str]],
            Field(description="Currencies or crypto symbols to include. Omit for all."),
        ] = None,
    ):
        """Get the latest exchange rates used by Finanze, as units of each currency (fiat, crypto or commodity) per 1 unit of base_currency. To convert an amount X in currency C to base, compute X / rates[C]."""
        base = await resolve_currency(ucs, base_currency)
        rates = await ucs.get_exchange_rates.execute()
        base_rates = rates.get(base)
        if base_rates is None:
            raise ToolError(f"No exchange rates available for {base}.")
        if currencies:
            wanted = {c.upper() for c in currencies}
            base_rates = {k: v for k, v in base_rates.items() if k.upper() in wanted}
        return {"base_currency": base, "rates": base_rates}

    @registry.read("Get Euribor rates")
    async def get_euribor_rates(
        last: Annotated[
            int, Field(ge=1, le=600, description="Number of latest entries.")
        ] = 24,
    ):
        """Get the latest Euribor rates by period, newest first."""
        history = await ucs.get_euribor_rates.execute()
        rates = sorted(history.rates, key=lambda r: r.period, reverse=True)
        return rates[:last]

    @registry.read("Search instruments", open_world=True)
    async def search_instruments(
        type: InstrumentType,
        name: InstrumentName = None,
        isin: InstrumentIsin = None,
        ticker: InstrumentTicker = None,
    ):
        """Search stocks, ETFs and mutual funds in external market data providers by name, ISIN or ticker, returning candidates with their latest price."""
        return await ucs.get_instruments.execute(
            _instrument_request(type, name, isin, ticker)
        )

    @registry.read("Get instrument details", open_world=True)
    async def get_instrument_details(
        type: InstrumentType,
        name: InstrumentName = None,
        isin: InstrumentIsin = None,
        ticker: InstrumentTicker = None,
    ):
        """Get the current price, currency and issuer of a stock, ETF or mutual fund from external market data providers."""
        info = await ucs.get_instrument_info.execute(
            _instrument_request(type, name, isin, ticker)
        )
        if info is None:
            raise ToolError("Instrument not found.")
        return info
