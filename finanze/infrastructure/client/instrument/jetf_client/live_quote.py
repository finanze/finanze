"""
https://github.com/druzsan/justetf-scraping
"""

import json
from typing import AsyncIterator, Optional

import asyncio
import websockets

from infrastructure.client.instrument.jetf_client.helpers import USER_AGENT
from infrastructure.client.instrument.jetf_client.jetf_types import (
    Quote,
    RawQuote,
    parse_quote,
)

WEBSOCKET_URL = "wss://api.mobile.stock-data-subscriptions.justetf.com/?subscription=trend&parameters=isins:{isin}/currency:EUR/language:en"


async def iterate_raw_live_quote(isin: str) -> AsyncIterator[RawQuote]:
    """
    Iterate over the live raw quote for the given ISIN. Updates are
    received automatically and their frequency cannot be controlled, also no
    updates besides the initial quote will be received outside of trade hours.

    For now, only EUR currency and gettex stock exchange are supported.

    Args:
        isin: The ISIN of the ETF.

    Yields:
        Raw live quote updates as `RawQuote`.
    """
    async with websockets.connect(
        WEBSOCKET_URL.format(isin=isin),
        additional_headers={
            "User-Agent": USER_AGENT,
            "Origin": "https://www.justetf.com",
        },
    ) as ws:
        async for message in ws:
            yield json.loads(message)


async def iterate_live_quote(isin: str) -> AsyncIterator[Quote]:
    """
    Iterate over the live quote for the given ISIN. Updates are
    received automatically and their frequency cannot be controlled, also no
    updates besides the initial quote will be received outside of trade hours.

    For now, only EUR currency and gettex stock exchange are supported.

    Args:
        isin: The ISIN of the ETF.

    Yields:
        Live quote updates as `Quote`.
    """
    async for raw_quote in iterate_raw_live_quote(isin):
        yield parse_quote(raw_quote)


async def load_raw_live_quote(isin: str) -> Optional[RawQuote]:
    """
    Load the last live raw quote for the given ISIN.

    For now, only EUR currency and gettex stock exchange are supported.

    Args:
        isin: The ISIN of the ETF.

    Returns:
        Raw live quote as `RawQuote`.
    """
    try:
        async with asyncio.timeout(2):
            async with websockets.connect(
                WEBSOCKET_URL.format(isin=isin),
                additional_headers={
                    "User-Agent": USER_AGENT,
                    "Origin": "https://www.justetf.com",
                },
            ) as ws:
                message = await ws.recv()
                return json.loads(message)
    except TimeoutError:
        return None


async def load_live_quote(isin: str) -> Optional[Quote]:
    """
    Load the live quote for the given ISIN.

    For now, only EUR currency and gettex stock exchange are supported.

    Args:
        isin: The ISIN of the ETF.

    Returns:
        Live quote as `Quote`.
    """
    raw_quote = await load_raw_live_quote(isin)
    if raw_quote is None:
        return None
    return parse_quote(raw_quote)
