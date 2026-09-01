from copy import deepcopy
from unittest.mock import AsyncMock

import pytest

from domain.crypto import CryptoCurrencyType, CryptoFetchRequest, CryptoPositionType
from domain.dezimal import Dezimal
from domain.exception.exceptions import AddressNotFound, ExternalIntegrationRequired
from domain.external_integration import ExternalIntegrationId
from infrastructure.client.crypto.zerion.zerion_client import ZerionClient
from infrastructure.client.entity.crypto.zerion.zerion_fetcher import (
    ZERION_GENERIC_ASSET_NAME,
    ZerionFetcher,
)

FAKE_ADDRESS = "0xFAKE0000000000000000000000000000000001"
SECOND_ADDRESS = "0xFAKE0000000000000000000000000000000002"
FAKE_API_KEY = "fake-zerion-api-key"

AUSDC_CONTRACT = "0xaaaa000000000000000000000000000000a001"
PENDLE_CONTRACT = "0xdddd000000000000000000000000000000d001"
STETH_CONTRACT = "0xeeee000000000000000000000000000000e001"
COMP_CONTRACT = "0xffff000000000000000000000000000000f001"
GHO_CONTRACT = "0x1111000000000000000000000000000000a002"
DAI_CONTRACT = "0x2222000000000000000000000000000000a003"
USDC_RECEIPT_CONTRACT = "0xcccc000000000000000000000000000000c001"
PEPE_CONTRACT = "0x3333000000000000000000000000000000a004"
SCAM_CONTRACT = "0x4444000000000000000000000000000000a005"

FUNGIBLE_ICON_URL = "https://fake-zerion-cdn.example/tokens/pepe.png"
PROTOCOL_ICON_URL = "https://fake-zerion-cdn.example/protocols/aave.png"


def _fungible_info(
    symbol, name, contract=None, chain="ethereum", decimals=18, icon_url=None
):
    implementations = []
    if contract is not None:
        implementations.append(
            {"address": contract, "chain_id": chain, "decimals": decimals}
        )
    info = {"symbol": symbol, "name": name, "implementations": implementations}
    if icon_url is not None:
        info["icon"] = {"url": icon_url}
    return info


def _position(
    item_id,
    position_type,
    symbol,
    name,
    value,
    numeric,
    contract=None,
    protocol=None,
    receipt_contract=None,
    chain="ethereum",
    attr_name=None,
    fungible_icon_url=None,
    app_icon_url=None,
):
    receipt = None
    if receipt_contract is not None:
        receipt = {
            "fungible_info": {
                "implementations": [{"address": receipt_contract, "chain_id": chain}]
            }
        }
    attributes = {
        "position_type": position_type,
        "value": value,
        "quantity": {"numeric": numeric, "float": float(numeric), "decimals": 18},
        "fungible_info": _fungible_info(
            symbol, name, contract, chain, icon_url=fungible_icon_url
        ),
        "protocol": protocol,
        "name": attr_name if attr_name is not None else name,
        "receipt": receipt,
        "flags": {"displayable": True, "is_trash": False},
    }
    if app_icon_url is not None:
        attributes["application_metadata"] = {"icon": {"url": app_icon_url}}
    return {
        "id": item_id,
        "attributes": attributes,
        "relationships": {"chain": {"data": {"type": "chains", "id": chain}}},
    }


def _complex_items():
    return [
        _position(
            "deposit-1",
            "deposit",
            "aUSDC",
            "Aave V3 USDC",
            1000.50,
            "1000.5",
            contract=AUSDC_CONTRACT,
            protocol="Aave V3",
            receipt_contract=USDC_RECEIPT_CONTRACT,
        ),
        _position(
            "investment-1",
            "investment",
            "PT-GHO",
            "Pendle PT GHO",
            500.25,
            "500.25",
            contract=PENDLE_CONTRACT,
            protocol="Pendle",
        ),
        _position(
            "staked-1",
            "staked",
            "stETH",
            "Lido Staked ETH",
            2000.00,
            "2000",
            contract=STETH_CONTRACT,
            protocol="Lido",
        ),
        _position(
            "reward-1",
            "reward",
            "COMP",
            "Compound Reward",
            10.00,
            "10",
            contract=COMP_CONTRACT,
            protocol="Compound",
        ),
        _position(
            "loan-1",
            "loan",
            "GHO",
            "Aave V3 GHO Debt",
            300.00,
            "300",
            contract=GHO_CONTRACT,
            protocol="Aave V3",
        ),
    ]


def _wallet_items():
    return [
        _position(
            "wallet-1",
            "wallet",
            "DAI",
            "Dai Stablecoin",
            50.00,
            "50",
            contract=DAI_CONTRACT,
        ),
        _position(
            "wallet-receipt-1",
            "wallet",
            "USDC",
            "USD Coin",
            1000.50,
            "1000.5",
            contract=USDC_RECEIPT_CONTRACT,
        ),
    ]


def _full_items():
    return _complex_items() + _wallet_items()


def _native_wallet_item():
    # Zerion reports native tokens (e.g. ETH) with an implementation entry
    # for their chain whose "address" is null rather than a hex string.
    return {
        "id": "wallet-native-1",
        "attributes": {
            "position_type": "wallet",
            "value": 1234.56,
            "quantity": {"numeric": "0.5", "float": 0.5, "decimals": 18},
            "fungible_info": {
                "symbol": "ETH",
                "name": "Ethereum",
                "implementations": [
                    {"address": None, "chain_id": "ethereum", "decimals": 18}
                ],
            },
            "protocol": None,
            "name": "Ethereum",
            "receipt": None,
            "flags": {"displayable": True, "is_trash": False},
        },
        "relationships": {"chain": {"data": {"type": "chains", "id": "ethereum"}}},
    }


def _malformed_item():
    # A structurally-unexpected Zerion record: "quantity" is missing from
    # attributes, which makes `_map_item` raise a KeyError.
    return {
        "id": "malformed-1",
        "attributes": {
            "position_type": "wallet",
            "value": 10.0,
            "fungible_info": _fungible_info("BAD", "Malformed Token"),
            "protocol": None,
            "name": "Malformed",
            "receipt": None,
            "flags": {"displayable": True, "is_trash": False},
        },
        "relationships": {"chain": {"data": {"type": "chains", "id": "ethereum"}}},
    }


def _request(include_wallet_tokens=False, integrations=None):
    if integrations is None:
        integrations = {ExternalIntegrationId.ZERION: {"api_key": FAKE_API_KEY}}
    return CryptoFetchRequest(
        integrations=integrations,
        addresses=[FAKE_ADDRESS],
        include_wallet_tokens=include_wallet_tokens,
    )


class TestZerionFetcherGuard:
    @pytest.mark.asyncio
    async def test_missing_zerion_integration_raises(self):
        client = ZerionClient()
        fetcher = ZerionFetcher(client)

        with pytest.raises(ExternalIntegrationRequired) as exc_info:
            await fetcher.fetch(_request(integrations={}))

        assert exc_info.value.required_integrations == [ExternalIntegrationId.ZERION]


class TestZerionFetcherAddressNotFound:
    @pytest.mark.asyncio
    async def test_bad_address_is_skipped_and_good_address_still_maps(self):
        # A 400 from Zerion on one address must not abort the whole entity
        # fetch: that address's result is None while the others proceed.
        good_items = _wallet_items()

        async def fake_fetch_positions(api_key, address, positions_filter):
            if address == FAKE_ADDRESS:
                raise AddressNotFound()
            return deepcopy(good_items)

        client = ZerionClient()
        client.fetch_positions = AsyncMock(side_effect=fake_fetch_positions)
        fetcher = ZerionFetcher(client)

        request = CryptoFetchRequest(
            integrations={ExternalIntegrationId.ZERION: {"api_key": FAKE_API_KEY}},
            addresses=[FAKE_ADDRESS, SECOND_ADDRESS],
            include_wallet_tokens=True,
        )

        result = await fetcher.fetch(request)

        assert result.results[FAKE_ADDRESS] is None
        good_result = result.results[SECOND_ADDRESS]
        assert good_result is not None
        assert {a.symbol for a in good_result.assets} == {"DAI", "USDC"}


class TestZerionFetcherIds:
    @pytest.mark.asyncio
    async def test_mapped_positions_have_unique_non_null_ids(self):
        # Regression: every fetched position must carry a unique, non-null id.
        # The save path inserts str(position.id) as the primary key, so a shared
        # or None id (str(None) == "None") triggers a UNIQUE constraint failure.
        client = ZerionClient()
        client.fetch_positions = AsyncMock(return_value=deepcopy(_full_items()))
        fetcher = ZerionFetcher(client)

        result = await fetcher.fetch(_request(include_wallet_tokens=True))

        assets = result.results[FAKE_ADDRESS].assets
        ids = [asset.id for asset in assets]
        assert len(assets) > 1
        assert all(asset_id is not None for asset_id in ids)
        assert len(ids) == len(set(ids))


class TestZerionFetcherOffMode:
    @pytest.mark.asyncio
    async def test_maps_positions_with_only_complex_filter(self):
        client = ZerionClient()
        client.fetch_positions = AsyncMock(return_value=deepcopy(_complex_items()))
        fetcher = ZerionFetcher(client)

        result = await fetcher.fetch(_request(include_wallet_tokens=False))

        client.fetch_positions.assert_awaited_once_with(
            FAKE_API_KEY, FAKE_ADDRESS, "only_complex"
        )

        assets = {a.symbol: a for a in result.results[FAKE_ADDRESS].assets}
        assert set(assets.keys()) == {"aUSDC", "PT-GHO", "stETH", "COMP", "GHO"}

        deposit = assets["aUSDC"]
        assert deposit.position_type == CryptoPositionType.SUPPLIED
        assert deposit.chain == "ethereum"
        assert deposit.protocol == "Aave V3"
        assert deposit.contract_address == AUSDC_CONTRACT
        assert deposit.type == CryptoCurrencyType.TOKEN
        assert deposit.balance == Dezimal("1000.5")
        assert deposit.market_value == Dezimal("1000.5")
        assert deposit.currency == "EUR"

        investment = assets["PT-GHO"]
        assert investment.position_type == CryptoPositionType.SUPPLIED
        assert investment.protocol == "Pendle"
        assert investment.contract_address == PENDLE_CONTRACT

        staked = assets["stETH"]
        assert staked.position_type == CryptoPositionType.STAKED
        assert staked.protocol == "Lido"

        reward = assets["COMP"]
        assert reward.position_type == CryptoPositionType.REWARD
        assert reward.protocol == "Compound"

        loan = assets["GHO"]
        assert loan.position_type == CryptoPositionType.BORROWED
        assert loan.balance == Dezimal("-300")
        assert loan.market_value == Dezimal("-300")
        assert loan.currency == "EUR"


class TestZerionFetcherOnMode:
    @pytest.mark.asyncio
    async def test_maps_positions_with_no_filter_and_dedups_receipt_wallet_token(self):
        client = ZerionClient()
        client.fetch_positions = AsyncMock(return_value=deepcopy(_full_items()))
        fetcher = ZerionFetcher(client)

        result = await fetcher.fetch(_request(include_wallet_tokens=True))

        client.fetch_positions.assert_awaited_once_with(
            FAKE_API_KEY, FAKE_ADDRESS, "no_filter"
        )

        assets = {a.symbol: a for a in result.results[FAKE_ADDRESS].assets}

        # Plain wallet token (not a receipt of any complex position) is kept.
        assert "DAI" in assets
        dai = assets["DAI"]
        assert dai.position_type == CryptoPositionType.HOLDING
        assert dai.type == CryptoCurrencyType.TOKEN
        assert dai.contract_address == DAI_CONTRACT

        # Wallet token that is also the receipt of the aUSDC deposit is dropped.
        assert "USDC" not in assets

        # Complex positions are unaffected by the dedup.
        assert set(assets.keys()) == {"aUSDC", "PT-GHO", "stETH", "COMP", "GHO", "DAI"}


class TestZerionFetcherReceiptDedupEdgeCases:
    @pytest.mark.asyncio
    async def test_receipt_from_unmapped_item_does_not_suppress_holding(self):
        shared = "0xrcpt0000000000000000000000000000000000"
        # A complex leg that fails to map (no "quantity") but carries a receipt,
        # plus a structurally broken item, plus a wallet holding at the receipt
        # address. The unmapped legs must neither crash the dedup nor suppress
        # the holding.
        broken_with_receipt = {
            "id": "broken-dep",
            "attributes": {
                "position_type": "deposit",
                "value": 100.0,
                "fungible_info": _fungible_info("aTOK", "Aave TOK", AUSDC_CONTRACT),
                "protocol": "Aave V3",
                "name": "Aave TOK",
                "receipt": {
                    "fungible_info": {
                        "implementations": [{"address": shared, "chain_id": "ethereum"}]
                    }
                },
                "flags": {"displayable": True, "is_trash": False},
            },
            "relationships": {"chain": {"data": {"type": "chains", "id": "ethereum"}}},
        }
        no_attributes = {"id": "no-attrs"}
        holding = _position(
            "wallet-tok", "wallet", "TOK", "Token", 50.0, "50", contract=shared
        )

        client = ZerionClient()
        client.fetch_positions = AsyncMock(
            return_value=[broken_with_receipt, no_attributes, deepcopy(holding)]
        )
        fetcher = ZerionFetcher(client)

        result = await fetcher.fetch(_request(include_wallet_tokens=True))

        assets = result.results[FAKE_ADDRESS].assets
        assert {a.symbol for a in assets} == {"TOK"}

    @pytest.mark.asyncio
    async def test_receipt_does_not_suppress_same_address_on_another_chain(self):
        shared = "0xshared00000000000000000000000000000000"
        items = [
            _position(
                "dep-eth",
                "deposit",
                "aTOK",
                "Aave TOK",
                1000.0,
                "1000",
                contract=AUSDC_CONTRACT,
                protocol="Aave V3",
                receipt_contract=shared,
                chain="ethereum",
            ),
            _position(
                "wallet-poly",
                "wallet",
                "TOK",
                "Token",
                50.0,
                "50",
                contract=shared,
                chain="polygon",
            ),
        ]

        client = ZerionClient()
        client.fetch_positions = AsyncMock(return_value=deepcopy(items))
        fetcher = ZerionFetcher(client)

        result = await fetcher.fetch(_request(include_wallet_tokens=True))

        pairs = {(a.symbol, a.chain) for a in result.results[FAKE_ADDRESS].assets}
        # The polygon holding shares the address of the ethereum receipt but is
        # a different chain, so it must be kept.
        assert ("TOK", "polygon") in pairs


class TestZerionFetcherNativeToken:
    @pytest.mark.asyncio
    async def test_null_address_implementation_maps_to_native_without_raising(self):
        client = ZerionClient()
        client.fetch_positions = AsyncMock(
            return_value=[deepcopy(_native_wallet_item())]
        )
        fetcher = ZerionFetcher(client)

        result = await fetcher.fetch(_request(include_wallet_tokens=True))

        assets = result.results[FAKE_ADDRESS].assets
        assert len(assets) == 1

        eth = assets[0]
        assert eth.symbol == "ETH"
        assert eth.contract_address is None
        assert eth.type == CryptoCurrencyType.NATIVE
        assert eth.position_type == CryptoPositionType.HOLDING
        assert eth.balance == Dezimal("0.5")


class TestZerionFetcherUnmappedRow:
    @pytest.mark.asyncio
    async def test_row_without_matching_implementation_maps_to_token(self):
        item = {
            "id": "vault-1",
            "attributes": {
                "position_type": "deposit",
                "value": 500.0,
                "quantity": {"numeric": "500", "float": 500.0, "decimals": 18},
                "fungible_info": {
                    "symbol": "vTOKEN",
                    "name": "Vault Share",
                    "implementations": [{"address": "0xabc", "chain_id": "polygon"}],
                },
                "protocol": "SomeVault",
                "name": "Some Vault",
                "receipt": None,
                "flags": {"displayable": True, "is_trash": False},
            },
            "relationships": {"chain": {"data": {"type": "chains", "id": "ethereum"}}},
        }

        client = ZerionClient()
        client.fetch_positions = AsyncMock(return_value=[item])
        fetcher = ZerionFetcher(client)

        result = await fetcher.fetch(_request(include_wallet_tokens=True))

        assets = result.results[FAKE_ADDRESS].assets
        assert len(assets) == 1
        asset = assets[0]
        assert asset.symbol == "vTOKEN"
        assert asset.contract_address is None
        assert asset.type == CryptoCurrencyType.TOKEN


class TestZerionFetcherMalformedItems:
    @pytest.mark.asyncio
    async def test_skips_unmappable_item_and_maps_the_rest(self, caplog):
        wallet_items = _wallet_items()
        items = [wallet_items[0], _malformed_item(), wallet_items[1]]

        client = ZerionClient()
        client.fetch_positions = AsyncMock(return_value=deepcopy(items))
        fetcher = ZerionFetcher(client)

        with caplog.at_level("WARNING"):
            result = await fetcher.fetch(_request(include_wallet_tokens=True))

        assets = result.results[FAKE_ADDRESS].assets
        assert {a.symbol for a in assets} == {"DAI", "USDC"}
        assert len(assets) == 2
        assert any("malformed-1" in record.getMessage() for record in caplog.records)

    @pytest.mark.asyncio
    async def test_skips_item_with_missing_symbol_and_maps_the_rest(self, caplog):
        # crypto_currency_positions.symbol is NOT NULL: a position whose
        # fungible_info has a name but no symbol key must be skipped
        # explicitly, and the rest of the batch still maps.
        no_symbol_item = deepcopy(_wallet_items()[0])
        no_symbol_item["id"] = "no-symbol-1"
        del no_symbol_item["attributes"]["fungible_info"]["symbol"]
        items = [no_symbol_item, _wallet_items()[1]]

        client = ZerionClient()
        client.fetch_positions = AsyncMock(return_value=deepcopy(items))
        fetcher = ZerionFetcher(client)

        with caplog.at_level("WARNING"):
            result = await fetcher.fetch(_request(include_wallet_tokens=True))

        assets = result.results[FAKE_ADDRESS].assets
        assert {a.symbol for a in assets} == {"USDC"}
        assert len(assets) == 1
        assert any("no-symbol-1" in record.getMessage() for record in caplog.records)


class TestZerionFetcherNameAndIcon:
    @pytest.mark.asyncio
    async def test_wallet_token_uses_fungible_name_and_icon(self):
        # Zerion reports the generic "Asset" name for plain wallet tokens;
        # the mapper should prefer the token's own fungible_info name and
        # icon instead.
        item = _position(
            "wallet-icon-1",
            "wallet",
            "PEPE",
            "Pepe",
            123.45,
            "1000000",
            contract=PEPE_CONTRACT,
            attr_name="Asset",
            fungible_icon_url=FUNGIBLE_ICON_URL,
        )

        client = ZerionClient()
        client.fetch_positions = AsyncMock(return_value=[deepcopy(item)])
        fetcher = ZerionFetcher(client)

        result = await fetcher.fetch(_request(include_wallet_tokens=True))

        asset = result.results[FAKE_ADDRESS].assets[0]
        assert asset.name == "Pepe"
        assert asset.icon_url == FUNGIBLE_ICON_URL

    @pytest.mark.asyncio
    async def test_complex_position_uses_attributes_name_and_protocol_icon(self):
        # Complex (DeFi) positions carry a descriptive attributes.name and,
        # when the fungible token itself has no icon, should fall back to
        # the protocol's application_metadata icon.
        item = _position(
            "deposit-icon-1",
            "deposit",
            "aUSDC",
            "aUSDC",
            1000.50,
            "1000.5",
            contract=AUSDC_CONTRACT,
            protocol="Aave V3",
            attr_name="Aave V3 USDC",
            app_icon_url=PROTOCOL_ICON_URL,
        )

        client = ZerionClient()
        client.fetch_positions = AsyncMock(return_value=[deepcopy(item)])
        fetcher = ZerionFetcher(client)

        result = await fetcher.fetch(_request(include_wallet_tokens=False))

        asset = result.results[FAKE_ADDRESS].assets[0]
        assert asset.name == "Aave V3 USDC"
        assert asset.icon_url == PROTOCOL_ICON_URL

    @pytest.mark.asyncio
    async def test_position_without_any_icon_has_none_icon_url(self):
        item = _position(
            "wallet-no-icon-1",
            "wallet",
            "DAI",
            "Dai Stablecoin",
            50.00,
            "50",
            contract=DAI_CONTRACT,
        )

        client = ZerionClient()
        client.fetch_positions = AsyncMock(return_value=[deepcopy(item)])
        fetcher = ZerionFetcher(client)

        result = await fetcher.fetch(_request(include_wallet_tokens=True))

        asset = result.results[FAKE_ADDRESS].assets[0]
        assert asset.icon_url is None

    @pytest.mark.asyncio
    async def test_none_shaped_icon_and_application_metadata_do_not_raise(self):
        # Some Zerion records carry explicit nulls (rather than omitted
        # keys) for icon/application_metadata; the mapper must not raise.
        item = deepcopy(_wallet_items()[0])
        item["attributes"]["fungible_info"]["icon"] = None
        item["attributes"]["application_metadata"] = None

        client = ZerionClient()
        client.fetch_positions = AsyncMock(return_value=[item])
        fetcher = ZerionFetcher(client)

        result = await fetcher.fetch(_request(include_wallet_tokens=True))

        asset = result.results[FAKE_ADDRESS].assets[0]
        assert asset.icon_url is None

    @pytest.mark.asyncio
    async def test_wallet_token_without_fungible_name_falls_back_to_symbol(self):
        # Regression: Zerion sets attributes.name="Asset" for essentially
        # every wallet-type position. When fungible_info has no name either
        # (realistic for spam/newly-listed/unindexed ERC-20s), name must not
        # end up None: crypto_currency_positions.name is NOT NULL, and a
        # None here raised an IntegrityError that aborted the whole
        # entity's save. Falling back to the symbol keeps it non-null.
        item = _position(
            "wallet-no-name-1",
            "wallet",
            "SCAM",
            None,
            5.0,
            "100",
            contract=SCAM_CONTRACT,
            attr_name=ZERION_GENERIC_ASSET_NAME,
        )
        del item["attributes"]["fungible_info"]["name"]

        client = ZerionClient()
        client.fetch_positions = AsyncMock(return_value=[deepcopy(item)])
        fetcher = ZerionFetcher(client)

        result = await fetcher.fetch(_request(include_wallet_tokens=True))

        asset = result.results[FAKE_ADDRESS].assets[0]
        assert asset.name == "SCAM"
        assert asset.name is not None
