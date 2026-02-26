from enum import Enum

from pydantic.dataclasses import dataclass

from domain.entity import Entity


class CoinType(str, Enum):
    BITCOIN = "BITCOIN"
    LITECOIN = "LITECOIN"


class ScriptType(str, Enum):
    P2PKH = "p2pkh"
    P2SH_P2WPKH = "p2sh-p2wpkh"
    P2WPKH = "p2wpkh"
    P2TR = "p2tr"


@dataclass(frozen=True)
class DerivedAddress:
    index: int
    path: str
    address: str
    pubkey: str
    change: int


@dataclass(frozen=True)
class DerivedAddressesResult:
    key_type: str
    script_type: ScriptType
    coin: CoinType
    receiving: list[DerivedAddress]
    change: list[DerivedAddress]
    base_path: str = ""


@dataclass(frozen=True)
class AddressDerivationRequest:
    xpub: str
    coin: CoinType
    receiving_range: tuple[int, int] = (0, 30)
    change_range: tuple[int, int] = (0, 30)
    script_type: ScriptType | None = None
    account: int = 0


@dataclass(frozen=True)
class AddressDerivationPreviewRequest:
    xpub: str
    entity: Entity
    range: int = 5
    script_type: ScriptType | None = None
    account: int = 0
