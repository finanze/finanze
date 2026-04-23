import hashlib
from dataclasses import dataclass

import base58
from application.ports.public_key_derivation import PublicKeyDerivation
from ecdsa import SECP256k1
from ecdsa.ellipticcurve import Point, INFINITY

from domain.public_key import (
    AddressDerivationRequest,
    DerivedAddressesResult,
    ScriptType,
    CoinType,
    DerivedAddress,
)
import infrastructure.crypto.bech32 as bech32


@dataclass(frozen=True)
class NetworkConfig:
    coin_type: int
    p2pkh_prefix: bytes
    p2sh_prefix: bytes
    bech32_hrp: str


NETWORK_CONFIGS: dict[CoinType, NetworkConfig] = {
    CoinType.BITCOIN: NetworkConfig(
        coin_type=0,
        p2pkh_prefix=b"\x00",
        p2sh_prefix=b"\x05",
        bech32_hrp="bc",
    ),
    CoinType.LITECOIN: NetworkConfig(
        coin_type=2,
        p2pkh_prefix=b"\x30",
        p2sh_prefix=b"\x32",
        bech32_hrp="ltc",
    ),
}

PURPOSE_BY_SCRIPT_TYPE: dict[ScriptType, int] = {
    ScriptType.P2PKH: 44,
    ScriptType.P2SH_P2WPKH: 49,
    ScriptType.P2WPKH: 84,
    ScriptType.P2TR: 86,
}

KEY_PREFIX_PATTERNS: dict[str, tuple[ScriptType, CoinType | None]] = {
    "xpub": (ScriptType.P2PKH, CoinType.BITCOIN),
    "ypub": (ScriptType.P2SH_P2WPKH, CoinType.BITCOIN),
    "zpub": (ScriptType.P2WPKH, None),
    "Ltub": (ScriptType.P2PKH, CoinType.LITECOIN),
    "Mtub": (ScriptType.P2SH_P2WPKH, CoinType.LITECOIN),
}


def get_network_config(network: CoinType) -> NetworkConfig:
    return NETWORK_CONFIGS[network]


def get_purpose(script_type: ScriptType) -> int:
    return PURPOSE_BY_SCRIPT_TYPE[script_type]


def decode_extended_key(key: str) -> tuple[bytes, bytes, bytes, int, int]:
    raw = base58.b58decode_check(key)
    version = raw[:4]
    depth = raw[4]
    child_index = int.from_bytes(raw[9:13], "big")
    chain_code = raw[13:45]
    key_data = raw[45:78]
    return version, chain_code, key_data, depth, child_index


def get_key_prefix(extended_key: str) -> str | None:
    for prefix in KEY_PREFIX_PATTERNS:
        if extended_key.startswith(prefix):
            return prefix
    return None


def get_extended_key_info(
    extended_key: str,
) -> tuple[str, ScriptType, CoinType | None] | None:
    prefix = get_key_prefix(extended_key)
    if prefix is None:
        return None
    script_type, network = KEY_PREFIX_PATTERNS[prefix]
    return prefix, script_type, network


def needs_hardened_derivation(extended_key: str, depth: int) -> bool:
    if depth >= 3:
        return False
    prefix = get_key_prefix(extended_key)
    if prefix in ("zpub", "ypub"):
        return False
    return True


def validate_network_matches_extended_key(extended_key: str, network: CoinType) -> None:
    info = get_extended_key_info(extended_key)
    if info is None:
        return
    _, _, detected_network = info
    if detected_network is not None and detected_network != network:
        raise ValueError(
            f"Network mismatch: key looks like {detected_network.value}, but network={network.value} was provided"
        )


def point_from_pubkey(pubkey: bytes) -> Point:
    if pubkey[0] == 0x04:
        x = int.from_bytes(pubkey[1:33], "big")
        y = int.from_bytes(pubkey[33:65], "big")
    elif pubkey[0] in (0x02, 0x03):
        x = int.from_bytes(pubkey[1:33], "big")
        p = SECP256k1.curve.p()
        y_squared = (pow(x, 3, p) + 7) % p
        y = pow(y_squared, (p + 1) // 4, p)
        if (y % 2) != (pubkey[0] - 2):
            y = p - y
    else:
        raise ValueError("Invalid public key format")
    return Point(SECP256k1.curve, x, y)


def point_to_compressed(point: Point) -> bytes:
    x_bytes = point.x().to_bytes(32, "big")
    prefix = b"\x02" if point.y() % 2 == 0 else b"\x03"
    return prefix + x_bytes


def derive_child_pubkey(
    parent_pubkey: bytes, chain_code: bytes, index: int
) -> tuple[bytes, bytes]:
    if index >= 0x80000000:
        raise ValueError("Cannot derive hardened child from public key")

    data = parent_pubkey + index.to_bytes(4, "big")

    import hmac as hmac_module

    h = hmac_module.new(chain_code, data, hashlib.sha512).digest()

    il = int.from_bytes(h[:32], "big")
    ir = h[32:]

    if il >= SECP256k1.order:
        raise ValueError(f"Invalid child key at index {index}: IL >= curve order")

    parent_point = point_from_pubkey(parent_pubkey)
    il_point = SECP256k1.generator * il
    child_point = parent_point + il_point

    if child_point == INFINITY:
        raise ValueError(f"Invalid child key at index {index}: point at infinity")

    child_pubkey = point_to_compressed(child_point)
    child_chain_code = ir

    return child_pubkey, child_chain_code


def _ripemd160(data: bytes) -> bytes:
    try:
        h = hashlib.new("ripemd160")
        h.update(data)
        return h.digest()
    except ValueError:
        from infrastructure.crypto.ripemd160 import ripemd160

        return ripemd160(data)


def hash160(data: bytes) -> bytes:
    sha256_hash = hashlib.sha256(data).digest()
    return _ripemd160(sha256_hash)


def pubkey_to_p2pkh(pubkey: bytes, network: CoinType) -> str:
    pubkey_hash = hash160(pubkey)
    config = get_network_config(network)
    prefix = config.p2pkh_prefix
    return base58.b58encode_check(prefix + pubkey_hash).decode()


def pubkey_to_p2sh_p2wpkh(pubkey: bytes, network: CoinType) -> str:
    pubkey_hash = hash160(pubkey)
    witness_program = b"\x00\x14" + pubkey_hash
    script_hash = hash160(witness_program)
    config = get_network_config(network)
    prefix = config.p2sh_prefix
    return base58.b58encode_check(prefix + script_hash).decode()


def bech32_polymod(values: list[int]) -> int:
    GEN = [0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3]
    chk = 1
    for v in values:
        b = chk >> 25
        chk = ((chk & 0x1FFFFFF) << 5) ^ v
        for i in range(5):
            chk ^= GEN[i] if ((b >> i) & 1) else 0
    return chk


def bech32_hrp_expand(hrp: str) -> list[int]:
    return [ord(x) >> 5 for x in hrp] + [0] + [ord(x) & 31 for x in hrp]


def bech32_create_checksum(hrp: str, data: list[int], spec: int) -> list[int]:
    values = bech32_hrp_expand(hrp) + data
    const = 0x2BC830A3 if spec == 2 else 1
    polymod = bech32_polymod(values + [0, 0, 0, 0, 0, 0]) ^ const
    return [(polymod >> 5 * (5 - i)) & 31 for i in range(6)]


def bech32_encode(hrp: str, witver: int, witprog: bytes) -> str:
    spec = 2 if witver > 0 else 1
    ret = bech32.convertbits(witprog, 8, 5)
    ret = [witver] + ret
    checksum = bech32_create_checksum(hrp, ret, spec)
    return hrp + "1" + "".join([bech32.CHARSET[d] for d in ret + checksum])


def bech32m_encode(hrp: str, witver: int, witprog: bytes) -> str:
    return bech32_encode(hrp, witver, witprog)


def pubkey_to_p2wpkh(pubkey: bytes, network: CoinType) -> str:
    pubkey_hash = hash160(pubkey)
    config = get_network_config(network)
    return bech32_encode(config.bech32_hrp, 0, pubkey_hash)


def pubkey_to_taproot_internal(pubkey: bytes) -> bytes:
    if len(pubkey) == 33:
        return pubkey[1:]
    elif len(pubkey) == 32:
        return pubkey
    else:
        raise ValueError(f"Invalid pubkey length: {len(pubkey)}")


def tagged_hash(tag: str, data: bytes) -> bytes:
    tag_hash = hashlib.sha256(tag.encode()).digest()
    return hashlib.sha256(tag_hash + tag_hash + data).digest()


def taproot_tweak_pubkey(pubkey: bytes) -> bytes:
    internal_key = pubkey_to_taproot_internal(pubkey)
    tweak_hash = tagged_hash("TapTweak", internal_key)

    x = int.from_bytes(internal_key, "big")
    p = SECP256k1.curve.p()
    y_squared = (pow(x, 3, p) + 7) % p
    y = pow(y_squared, (p + 1) // 4, p)
    if y % 2 != 0:
        y = p - y

    P = Point(SECP256k1.curve, x, y)
    t = int.from_bytes(tweak_hash, "big") % SECP256k1.order
    Q = P + SECP256k1.generator * t
    x_bytes = Q.x().to_bytes(32, "big")
    return x_bytes


def pubkey_to_p2tr(pubkey: bytes, network: CoinType) -> str:
    tweaked_pubkey = taproot_tweak_pubkey(pubkey)
    config = get_network_config(network)
    return bech32m_encode(config.bech32_hrp, 1, tweaked_pubkey)


def derive_path_levels(
    pubkey: bytes,
    chain_code: bytes,
    levels: list[int],
) -> tuple[bytes, bytes]:
    current_pubkey = pubkey
    current_chain = chain_code
    for index in levels:
        current_pubkey, current_chain = derive_child_pubkey(
            current_pubkey, current_chain, index
        )
    return current_pubkey, current_chain


def build_derivation_path(
    depth: int,
    script_type: ScriptType,
    network: CoinType,
    account: int = 0,
    derive_hardened: bool = True,
) -> tuple[list[int], str]:
    purpose = get_purpose(script_type)
    coin_type = get_network_config(network).coin_type

    if derive_hardened:
        if depth < 3:
            raise ValueError(
                "Cannot derive hardened account-level paths from a master or intermediate public key. "
                "An account-level extended public key (depth >= 3) is required."
            )
        base_path = f"m/{purpose}'/{coin_type}'/{account}'"
        levels = []
    else:
        if depth >= 3:
            base_path = f"m/{purpose}'/{coin_type}'/{account}'"
        else:
            base_path = "m"
        levels = []

    return levels, base_path


def derive_addresses(
    extended_key: str,
    network: CoinType,
    script_type: ScriptType,
    change: int = 0,
    start_index: int = 0,
    count: int = 30,
) -> tuple[list[DerivedAddress], str]:
    validate_network_matches_extended_key(extended_key, network)

    _, chain_code, key_data, depth, child_index = decode_extended_key(extended_key)

    if key_data[0] == 0x00:
        pubkey = key_data[1:]
    else:
        pubkey = key_data

    if len(pubkey) == 32:
        raise ValueError("This appears to be an extended private key, not a public key")

    account = 0
    if depth == 3:
        hardened_bit = 0x80000000
        if child_index >= hardened_bit:
            account = child_index - hardened_bit
        else:
            account = child_index

    derive_hardened = needs_hardened_derivation(extended_key, depth)
    levels_to_derive, base_path = build_derivation_path(
        depth, script_type, network, account, derive_hardened
    )

    current_pubkey, current_chain = derive_path_levels(
        pubkey, chain_code, levels_to_derive
    )
    current_pubkey, current_chain = derive_child_pubkey(
        current_pubkey, current_chain, change
    )

    addresses: list[DerivedAddress] = []
    end_index = start_index + count
    for i in range(start_index, end_index):
        child_pubkey, _ = derive_child_pubkey(current_pubkey, current_chain, i)

        if script_type == ScriptType.P2PKH:
            addr = pubkey_to_p2pkh(child_pubkey, network)
        elif script_type == ScriptType.P2SH_P2WPKH:
            addr = pubkey_to_p2sh_p2wpkh(child_pubkey, network)
        elif script_type == ScriptType.P2WPKH:
            addr = pubkey_to_p2wpkh(child_pubkey, network)
        elif script_type == ScriptType.P2TR:
            addr = pubkey_to_p2tr(child_pubkey, network)
        else:
            addr = pubkey_to_p2pkh(child_pubkey, network)

        full_path = f"{base_path}/{change}/{i}"
        addresses.append(
            DerivedAddress(
                index=i,
                path=full_path,
                address=addr,
                pubkey=child_pubkey.hex(),
                change=change,
            )
        )

    return addresses, base_path


class PublicKeyDerivationAdapter(PublicKeyDerivation):
    def calculate(self, request: AddressDerivationRequest) -> DerivedAddressesResult:
        validate_network_matches_extended_key(request.xpub, request.coin)

        key_info = get_extended_key_info(request.xpub)
        if key_info:
            key_type, detected_script_type, _ = key_info
        else:
            key_type = "unknown"
            detected_script_type = ScriptType.P2PKH

        script_type = (
            request.script_type if request.script_type else detected_script_type
        )

        receiving_start, receiving_end = request.receiving_range
        if receiving_end < receiving_start:
            raise ValueError("receiving_range end must be >= start")

        receiving, base_path = derive_addresses(
            request.xpub,
            network=request.coin,
            script_type=script_type,
            change=0,
            start_index=receiving_start,
            count=receiving_end - receiving_start,
        )

        change_start, change_end = request.change_range
        if change_end < change_start:
            raise ValueError("change_range end must be >= start")

        change_addrs, _ = derive_addresses(
            request.xpub,
            network=request.coin,
            script_type=script_type,
            change=1,
            start_index=change_start,
            count=change_end - change_start,
        )

        return DerivedAddressesResult(
            key_type=key_type,
            script_type=script_type,
            coin=request.coin,
            receiving=receiving,
            change=change_addrs,
            base_path=base_path,
        )
