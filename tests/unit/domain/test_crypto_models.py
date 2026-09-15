from uuid import uuid4

from domain.crypto import (
    AddressSource,
    ConnectCryptoWallet,
    CryptoFetchedPosition,
    CryptoFetchRequest,
    CryptoPositionType,
    CryptoCurrencyType,
    CryptoWallet,
)
from domain.global_position import CryptoCurrencyPosition
from domain.dezimal import Dezimal


def test_position_type_values():
    assert {t.value for t in CryptoPositionType} == {
        "HOLDING",
        "SUPPLIED",
        "BORROWED",
        "STAKED",
        "LP",
        "REWARD",
    }


def test_fetched_position_defaults_backward_compatible():
    p = CryptoFetchedPosition(
        id=None, symbol="ETH", balance=Dezimal("1"), type=CryptoCurrencyType.NATIVE
    )
    assert p.position_type == CryptoPositionType.HOLDING
    assert p.chain is None and p.protocol is None
    assert p.market_value is None and p.currency is None


def test_defi_fetched_position_carries_value_and_labels():
    p = CryptoFetchedPosition(
        id=None,
        symbol="aUSDC",
        balance=Dezimal("100"),
        type=CryptoCurrencyType.TOKEN,
        chain="ethereum",
        protocol="Aave V3",
        position_type=CryptoPositionType.SUPPLIED,
        market_value=Dezimal("100.10"),
        currency="EUR",
    )
    assert p.protocol == "Aave V3" and p.position_type == CryptoPositionType.SUPPLIED


def test_stored_position_accepts_labels():
    p = CryptoCurrencyPosition(
        id=None,
        symbol="debtUSDC",
        amount=Dezimal("-50"),
        type=CryptoCurrencyType.TOKEN,
        chain="ethereum",
        protocol="Aave V3",
        position_type=CryptoPositionType.BORROWED,
        market_value=Dezimal("-50.00"),
        currency="EUR",
    )
    assert p.market_value == Dezimal("-50.00")


def test_connect_crypto_wallet_include_wallet_tokens_defaults_false():
    connect = ConnectCryptoWallet(
        entity_id=uuid4(),
        addresses=["0xabc"],
        name="My Wallet",
        address_source=AddressSource.MANUAL,
    )
    assert connect.include_wallet_tokens is False


def test_connect_crypto_wallet_include_wallet_tokens_accepts_true():
    connect = ConnectCryptoWallet(
        entity_id=uuid4(),
        addresses=["0xabc"],
        name="My Wallet",
        address_source=AddressSource.MANUAL,
        include_wallet_tokens=True,
    )
    assert connect.include_wallet_tokens is True


def test_crypto_wallet_include_wallet_tokens_defaults_false():
    wallet = CryptoWallet(
        id=uuid4(),
        entity_id=uuid4(),
        addresses=["0xabc"],
        name="My Wallet",
        address_source=AddressSource.MANUAL,
        hd_wallet=None,
    )
    assert wallet.include_wallet_tokens is False


def test_crypto_wallet_include_wallet_tokens_accepts_true():
    wallet = CryptoWallet(
        id=uuid4(),
        entity_id=uuid4(),
        addresses=["0xabc"],
        name="My Wallet",
        address_source=AddressSource.MANUAL,
        hd_wallet=None,
        include_wallet_tokens=True,
    )
    assert wallet.include_wallet_tokens is True


def test_crypto_fetch_request_include_wallet_tokens_defaults_false():
    request = CryptoFetchRequest(integrations={})
    assert request.include_wallet_tokens is False


def test_crypto_fetch_request_include_wallet_tokens_accepts_true():
    request = CryptoFetchRequest(integrations={}, include_wallet_tokens=True)
    assert request.include_wallet_tokens is True
