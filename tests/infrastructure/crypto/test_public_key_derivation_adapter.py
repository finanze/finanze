import base58
import pytest

from domain.public_key import (
    AddressDerivationRequest,
    CoinType,
    ScriptType,
)
from infrastructure.crypto.public_key_derivation_adapter import (
    PublicKeyDerivationAdapter,
    decode_extended_key,
    derive_addresses,
    derive_child_pubkey,
    derive_path_levels,
    build_derivation_path,
    get_network_config,
    get_purpose,
    get_extended_key_info,
    get_key_prefix,
    needs_hardened_derivation,
    hash160,
    point_from_pubkey,
    point_to_compressed,
    pubkey_to_p2pkh,
    pubkey_to_p2sh_p2wpkh,
    pubkey_to_p2wpkh,
    pubkey_to_p2tr,
    pubkey_to_taproot_internal,
    taproot_tweak_pubkey,
    validate_network_matches_extended_key,
    NETWORK_CONFIGS,
    PURPOSE_BY_SCRIPT_TYPE,
    KEY_PREFIX_PATTERNS,
)

VALID_BTC_XPUB = "xpub661MyMwAqRbcFtXgS5sYJABqqG9YLmC4Q1Rdap9gSE8NqtwybGhePY2gZ29ESFjqJoCu1Rupje8YtGqsefD265TMg7usUDFdp6W1EGMcet8"
VALID_BTC_YPUB = "ypub6Ww3ibxVfGzLrAH1PNcjyAWenMTbbAosGNB6VvmSEgytSER9azLDWCxoJwW7Ke7icmizBMXrzBx9979FfaHxHcrArf3zbeJJJUZPf663zsP"
VALID_BTC_ZPUB = "zpub6rFR7y4Q2AijBEqTUquhVz398htDFrtymD9xYYfG1m4wAcvPhXNfE3EfH1r1ADqtfSdVCToUG868RvUUkgDKf31mGDtKsAYz2oz2AGutZYs"


VALID_ELECTRUM_ZPUB = "zpub6nCvPheBJa1JynNZn2t29jdYX444VGohf6i3aYWEsTEBQE2BHDRE7cyT8R9LGSPBbaHvR4eFvsrLBotW5HME8WBGnc6LbGdvXtNhPWuMPbz"


def _build_depth2_xpub(root_xpub: str, account: int = 0) -> str:
    version, chain_code, key_data, _, _ = decode_extended_key(root_xpub)
    pubkey = key_data[1:] if key_data[0] == 0x00 else key_data
    child1_pubkey, child1_chain = derive_child_pubkey(pubkey, chain_code, 0)
    child2_pubkey, child2_chain = derive_child_pubkey(child1_pubkey, child1_chain, 0)
    fingerprint = hash160(child1_pubkey)[:4]
    child_index = (0x80000000 + account).to_bytes(4, "big")
    raw = version + b"\x02" + fingerprint + child_index + child2_chain + child2_pubkey
    return base58.b58encode_check(raw).decode()


class TestDecodeExtendedKey:
    def test_decode_valid_xpub(self):
        version, chain_code, key_data, depth, child_index = decode_extended_key(
            VALID_BTC_XPUB
        )

        assert version == b"\x04\x88\xb2\x1e"
        assert len(chain_code) == 32
        assert len(key_data) == 33
        assert depth == 0
        assert child_index == 0

    def test_decode_valid_ypub(self):
        version, chain_code, key_data, depth, child_index = decode_extended_key(
            VALID_BTC_YPUB
        )

        assert version == b"\x04\x9d\x7c\xb2"
        assert len(chain_code) == 32
        assert len(key_data) == 33

    def test_decode_valid_zpub(self):
        version, chain_code, key_data, depth, child_index = decode_extended_key(
            VALID_BTC_ZPUB
        )

        assert version == b"\x04\xb2\x47\x46"
        assert len(chain_code) == 32
        assert len(key_data) == 33

    def test_decode_electrum_zpub(self):
        version, chain_code, key_data, depth, child_index = decode_extended_key(
            VALID_ELECTRUM_ZPUB
        )

        assert version == b"\x04\xb2\x47\x46"
        assert len(chain_code) == 32
        assert len(key_data) == 33
        assert depth == 1

    def test_decode_invalid_key_raises_exception(self):
        with pytest.raises(Exception):
            decode_extended_key("invalid_key")


class TestValidateNetworkMatchesExtendedKey:
    def test_btc_xpub_with_btc_network_passes(self):
        validate_network_matches_extended_key(VALID_BTC_XPUB, CoinType.BITCOIN)

    def test_btc_xpub_with_ltc_network_raises(self):
        with pytest.raises(ValueError, match="Network mismatch"):
            validate_network_matches_extended_key(VALID_BTC_XPUB, CoinType.LITECOIN)

    def test_invalid_key_does_not_raise(self):
        validate_network_matches_extended_key("invalid_key", CoinType.BITCOIN)


class TestHash160:
    def test_hash160_produces_20_byte_output(self):
        data = b"test data"
        result = hash160(data)

        assert len(result) == 20

    def test_hash160_is_deterministic(self):
        data = b"test data"
        result1 = hash160(data)
        result2 = hash160(data)

        assert result1 == result2

    def test_hash160_different_input_different_output(self):
        result1 = hash160(b"data1")
        result2 = hash160(b"data2")

        assert result1 != result2


class TestPointFromPubkey:
    def test_compressed_pubkey_02_prefix(self):
        pubkey = bytes.fromhex(
            "0279BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798"
        )
        point = point_from_pubkey(pubkey)

        assert point is not None
        assert point.x() == int.from_bytes(pubkey[1:33], "big")

    def test_compressed_pubkey_03_prefix(self):
        pubkey = bytes.fromhex(
            "03D90CD625EE87DD38656DD95CF79F65F60F7273B67D3096E68BD81E4F5342691F"
        )
        point = point_from_pubkey(pubkey)

        assert point is not None

    def test_invalid_prefix_raises(self):
        pubkey = bytes.fromhex(
            "05D90CD625EE87DD38656DD95CF79F65F60F7273B67D3096E68BD81E4F5342691F"
        )

        with pytest.raises(ValueError, match="Invalid public key format"):
            point_from_pubkey(pubkey)


class TestPointToCompressed:
    def test_even_y_produces_02_prefix(self):
        pubkey = bytes.fromhex(
            "0279BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798"
        )
        point = point_from_pubkey(pubkey)
        compressed = point_to_compressed(point)

        assert compressed[0] in (0x02, 0x03)
        assert len(compressed) == 33


class TestDeriveChildPubkey:
    def test_derive_non_hardened_child(self):
        _, chain_code, key_data, _, _ = decode_extended_key(VALID_BTC_XPUB)
        pubkey = key_data[1:] if key_data[0] == 0x00 else key_data

        child_pubkey, child_chain = derive_child_pubkey(pubkey, chain_code, 0)

        assert len(child_pubkey) == 33
        assert len(child_chain) == 32

    def test_derive_hardened_child_raises(self):
        _, chain_code, key_data, _, _ = decode_extended_key(VALID_BTC_XPUB)
        pubkey = key_data[1:] if key_data[0] == 0x00 else key_data
        hardened_index = 0x80000000

        with pytest.raises(ValueError, match="Cannot derive hardened child"):
            derive_child_pubkey(pubkey, chain_code, hardened_index)

    def test_derive_different_indexes_produce_different_keys(self):
        _, chain_code, key_data, _, _ = decode_extended_key(VALID_BTC_XPUB)
        pubkey = key_data[1:] if key_data[0] == 0x00 else key_data

        child_pubkey_0, _ = derive_child_pubkey(pubkey, chain_code, 0)
        child_pubkey_1, _ = derive_child_pubkey(pubkey, chain_code, 1)

        assert child_pubkey_0 != child_pubkey_1


class TestPubkeyToP2PKH:
    def test_btc_p2pkh_address_starts_with_1(self):
        _, chain_code, key_data, _, _ = decode_extended_key(VALID_BTC_XPUB)
        pubkey = key_data[1:] if key_data[0] == 0x00 else key_data
        child_pubkey, _ = derive_child_pubkey(pubkey, chain_code, 0)

        address = pubkey_to_p2pkh(child_pubkey, CoinType.BITCOIN)

        assert address.startswith("1")

    def test_ltc_p2pkh_address_starts_with_L(self):
        _, chain_code, key_data, _, _ = decode_extended_key(VALID_BTC_XPUB)
        pubkey = key_data[1:] if key_data[0] == 0x00 else key_data
        child_pubkey, _ = derive_child_pubkey(pubkey, chain_code, 0)

        address = pubkey_to_p2pkh(child_pubkey, CoinType.LITECOIN)

        assert address.startswith("L")


class TestPubkeyToP2SHP2WPKH:
    def test_btc_p2sh_address_starts_with_3(self):
        _, chain_code, key_data, _, _ = decode_extended_key(VALID_BTC_YPUB)
        pubkey = key_data[1:] if key_data[0] == 0x00 else key_data
        child_pubkey, _ = derive_child_pubkey(pubkey, chain_code, 0)

        address = pubkey_to_p2sh_p2wpkh(child_pubkey, CoinType.BITCOIN)

        assert address.startswith("3")


class TestPubkeyToP2WPKH:
    def test_btc_p2wpkh_address_starts_with_bc1q(self):
        _, chain_code, key_data, _, _ = decode_extended_key(VALID_BTC_ZPUB)
        pubkey = key_data[1:] if key_data[0] == 0x00 else key_data
        child_pubkey, _ = derive_child_pubkey(pubkey, chain_code, 0)

        address = pubkey_to_p2wpkh(child_pubkey, CoinType.BITCOIN)

        assert address.startswith("bc1q")

    def test_ltc_p2wpkh_address_starts_with_ltc1q(self):
        _, chain_code, key_data, _, _ = decode_extended_key(VALID_BTC_ZPUB)
        pubkey = key_data[1:] if key_data[0] == 0x00 else key_data
        child_pubkey, _ = derive_child_pubkey(pubkey, chain_code, 0)

        address = pubkey_to_p2wpkh(child_pubkey, CoinType.LITECOIN)

        assert address.startswith("ltc1q")


class TestPubkeyToTaproot:
    def test_btc_p2tr_address_starts_with_bc1p(self):
        _, chain_code, key_data, _, _ = decode_extended_key(VALID_BTC_ZPUB)
        pubkey = key_data[1:] if key_data[0] == 0x00 else key_data
        child_pubkey, _ = derive_child_pubkey(pubkey, chain_code, 0)

        address = pubkey_to_p2tr(child_pubkey, CoinType.BITCOIN)

        assert address.startswith("bc1p")


class TestPubkeyToTaprootInternal:
    def test_33_byte_pubkey_returns_32_bytes(self):
        pubkey = bytes.fromhex(
            "0279BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798"
        )
        result = pubkey_to_taproot_internal(pubkey)

        assert len(result) == 32

    def test_32_byte_pubkey_returns_same(self):
        pubkey = bytes.fromhex(
            "79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798"
        )
        result = pubkey_to_taproot_internal(pubkey)

        assert result == pubkey

    def test_invalid_length_raises(self):
        pubkey = bytes.fromhex(
            "79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F817"
        )

        with pytest.raises(ValueError, match="Invalid pubkey length"):
            pubkey_to_taproot_internal(pubkey)


class TestTaprootTweakPubkey:
    def test_produces_32_byte_output(self):
        pubkey = bytes.fromhex(
            "0279BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798"
        )
        result = taproot_tweak_pubkey(pubkey)

        assert len(result) == 32


class TestDeriveAddresses:
    def test_derive_btc_p2pkh_addresses(self):
        addresses, base_path = derive_addresses(
            VALID_BTC_XPUB,
            network=CoinType.BITCOIN,
            script_type=ScriptType.P2PKH,
            change=0,
            start_index=0,
            count=5,
        )

        assert len(addresses) == 5
        assert "44'" in base_path
        for i, addr in enumerate(addresses):
            assert addr.index == i
            assert addr.address.startswith("1")
            assert len(addr.pubkey) == 66

    def test_derive_btc_p2sh_p2wpkh_addresses(self):
        addresses, _ = derive_addresses(
            VALID_BTC_YPUB,
            network=CoinType.BITCOIN,
            script_type=ScriptType.P2SH_P2WPKH,
            change=0,
            start_index=0,
            count=3,
        )

        assert len(addresses) == 3
        for addr in addresses:
            assert addr.address.startswith("3")

    def test_derive_btc_p2wpkh_addresses(self):
        addresses, _ = derive_addresses(
            VALID_BTC_ZPUB,
            network=CoinType.BITCOIN,
            script_type=ScriptType.P2WPKH,
            change=0,
            start_index=0,
            count=3,
        )

        assert len(addresses) == 3
        for addr in addresses:
            assert addr.address.startswith("bc1q")

    def test_derive_btc_p2tr_addresses(self):
        addresses, _ = derive_addresses(
            VALID_BTC_ZPUB,
            network=CoinType.BITCOIN,
            script_type=ScriptType.P2TR,
            change=0,
            start_index=0,
            count=3,
        )

        assert len(addresses) == 3
        for addr in addresses:
            assert addr.address.startswith("bc1p")

    def test_derive_change_addresses(self):
        receiving, _ = derive_addresses(
            VALID_BTC_XPUB,
            network=CoinType.BITCOIN,
            script_type=ScriptType.P2PKH,
            change=0,
            start_index=0,
            count=1,
        )
        change, _ = derive_addresses(
            VALID_BTC_XPUB,
            network=CoinType.BITCOIN,
            script_type=ScriptType.P2PKH,
            change=1,
            start_index=0,
            count=1,
        )

        assert receiving[0].address != change[0].address
        assert receiving[0].change == 0
        assert change[0].change == 1

    def test_derive_with_start_index(self):
        addresses, _ = derive_addresses(
            VALID_BTC_XPUB,
            network=CoinType.BITCOIN,
            script_type=ScriptType.P2PKH,
            start_index=10,
            count=3,
        )

        assert addresses[0].index == 10
        assert addresses[1].index == 11
        assert addresses[2].index == 12

    def test_network_mismatch_raises(self):
        with pytest.raises(ValueError, match="Network mismatch"):
            derive_addresses(
                VALID_BTC_XPUB,
                network=CoinType.LITECOIN,
                script_type=ScriptType.P2PKH,
            )

    def test_derive_with_custom_account(self):
        addresses_acc0, base_path_0 = derive_addresses(
            VALID_BTC_XPUB,
            network=CoinType.BITCOIN,
            script_type=ScriptType.P2PKH,
            account=0,
            count=2,
        )
        addresses_acc1, base_path_1 = derive_addresses(
            VALID_BTC_XPUB,
            network=CoinType.BITCOIN,
            script_type=ScriptType.P2PKH,
            account=1,
            count=2,
        )

        assert "0'" in base_path_0
        assert "1'" in base_path_1
        assert addresses_acc0[0].address != addresses_acc1[0].address

    def test_account_inferred_from_xpub_at_depth_2(self):
        depth_2_xpub = _build_depth2_xpub(VALID_BTC_XPUB, account=3)

        _, _, _, depth, child_index = decode_extended_key(depth_2_xpub)
        assert depth == 2
        assert child_index == 0x80000000 + 3

        addresses, base_path = derive_addresses(
            depth_2_xpub,
            network=CoinType.BITCOIN,
            script_type=ScriptType.P2PKH,
            account=99,
            count=1,
        )

        assert "3'" in base_path


class TestPublicKeyDerivationAdapter:
    @pytest.fixture
    def adapter(self):
        return PublicKeyDerivationAdapter()

    def test_calculate_with_xpub(self, adapter):
        request = AddressDerivationRequest(
            xpub=VALID_BTC_XPUB,
            coin=CoinType.BITCOIN,
            receiving_range=(0, 5),
            change_range=(0, 3),
        )

        result = adapter.calculate(request)

        assert result.key_type == "xpub"
        assert result.script_type == ScriptType.P2PKH
        assert result.coin == CoinType.BITCOIN
        assert len(result.receiving) == 5
        assert len(result.change) == 3
        assert result.base_path != ""

    def test_calculate_with_ypub(self, adapter):
        request = AddressDerivationRequest(
            xpub=VALID_BTC_YPUB,
            coin=CoinType.BITCOIN,
            receiving_range=(0, 3),
            change_range=(0, 2),
        )

        result = adapter.calculate(request)

        assert result.key_type == "ypub"
        assert result.script_type == ScriptType.P2SH_P2WPKH
        assert len(result.receiving) == 3
        for addr in result.receiving:
            assert addr.address.startswith("3")

    def test_calculate_with_zpub(self, adapter):
        request = AddressDerivationRequest(
            xpub=VALID_BTC_ZPUB,
            coin=CoinType.BITCOIN,
            receiving_range=(0, 3),
            change_range=(0, 2),
        )

        result = adapter.calculate(request)

        assert result.key_type == "zpub"
        assert result.script_type == ScriptType.P2WPKH
        for addr in result.receiving:
            assert addr.address.startswith("bc1q")

    def test_calculate_with_script_type_override(self, adapter):
        request = AddressDerivationRequest(
            xpub=VALID_BTC_XPUB,
            coin=CoinType.BITCOIN,
            receiving_range=(0, 3),
            change_range=(0, 2),
            script_type=ScriptType.P2TR,
        )

        result = adapter.calculate(request)

        assert result.script_type == ScriptType.P2TR
        for addr in result.receiving:
            assert addr.address.startswith("bc1p")

    def test_calculate_invalid_receiving_range_raises(self, adapter):
        request = AddressDerivationRequest(
            xpub=VALID_BTC_XPUB,
            coin=CoinType.BITCOIN,
            receiving_range=(10, 5),
            change_range=(0, 2),
        )

        with pytest.raises(ValueError, match="receiving_range end must be >= start"):
            adapter.calculate(request)

    def test_calculate_invalid_change_range_raises(self, adapter):
        request = AddressDerivationRequest(
            xpub=VALID_BTC_XPUB,
            coin=CoinType.BITCOIN,
            receiving_range=(0, 5),
            change_range=(10, 5),
        )

        with pytest.raises(ValueError, match="change_range end must be >= start"):
            adapter.calculate(request)

    def test_calculate_network_mismatch_raises(self, adapter):
        request = AddressDerivationRequest(
            xpub=VALID_BTC_XPUB,
            coin=CoinType.LITECOIN,
            receiving_range=(0, 5),
            change_range=(0, 2),
        )

        with pytest.raises(ValueError, match="Network mismatch"):
            adapter.calculate(request)

    def test_calculate_produces_unique_addresses(self, adapter):
        request = AddressDerivationRequest(
            xpub=VALID_BTC_XPUB,
            coin=CoinType.BITCOIN,
            receiving_range=(0, 10),
            change_range=(0, 10),
        )

        result = adapter.calculate(request)

        all_addresses = [a.address for a in result.receiving] + [
            a.address for a in result.change
        ]
        assert len(all_addresses) == len(set(all_addresses))

    def test_calculate_is_deterministic(self, adapter):
        request = AddressDerivationRequest(
            xpub=VALID_BTC_XPUB,
            coin=CoinType.BITCOIN,
            receiving_range=(0, 5),
            change_range=(0, 3),
        )

        result1 = adapter.calculate(request)
        result2 = adapter.calculate(request)

        assert [a.address for a in result1.receiving] == [
            a.address for a in result2.receiving
        ]
        assert [a.address for a in result1.change] == [
            a.address for a in result2.change
        ]

    def test_calculate_with_custom_account(self, adapter):
        request_acc0 = AddressDerivationRequest(
            xpub=VALID_BTC_XPUB,
            coin=CoinType.BITCOIN,
            receiving_range=(0, 2),
            change_range=(0, 1),
            account=0,
        )
        request_acc1 = AddressDerivationRequest(
            xpub=VALID_BTC_XPUB,
            coin=CoinType.BITCOIN,
            receiving_range=(0, 2),
            change_range=(0, 1),
            account=1,
        )

        result0 = adapter.calculate(request_acc0)
        result1 = adapter.calculate(request_acc1)

        assert result0.receiving[0].address != result1.receiving[0].address


class TestGetPurpose:
    def test_p2pkh_returns_44(self):
        assert get_purpose(ScriptType.P2PKH) == 44

    def test_p2sh_p2wpkh_returns_49(self):
        assert get_purpose(ScriptType.P2SH_P2WPKH) == 49

    def test_p2wpkh_returns_84(self):
        assert get_purpose(ScriptType.P2WPKH) == 84

    def test_p2tr_returns_86(self):
        assert get_purpose(ScriptType.P2TR) == 86


class TestGetNetworkConfig:
    def test_btc_returns_correct_config(self):
        config = get_network_config(CoinType.BITCOIN)
        assert config.coin_type == 0
        assert config.p2pkh_prefix == b"\x00"
        assert config.p2sh_prefix == b"\x05"
        assert config.bech32_hrp == "bc"

    def test_ltc_returns_correct_config(self):
        config = get_network_config(CoinType.LITECOIN)
        assert config.coin_type == 2
        assert config.p2pkh_prefix == b"\x30"
        assert config.p2sh_prefix == b"\x32"
        assert config.bech32_hrp == "ltc"


class TestDerivePathLevels:
    def test_derive_single_level(self):
        _, chain_code, key_data, _, _ = decode_extended_key(VALID_BTC_XPUB)
        pubkey = key_data[1:] if key_data[0] == 0x00 else key_data

        result_pubkey, result_chain = derive_path_levels(pubkey, chain_code, [0])

        assert len(result_pubkey) == 33
        assert len(result_chain) == 32

    def test_derive_multiple_levels(self):
        _, chain_code, key_data, _, _ = decode_extended_key(VALID_BTC_XPUB)
        pubkey = key_data[1:] if key_data[0] == 0x00 else key_data

        result_pubkey, result_chain = derive_path_levels(pubkey, chain_code, [0, 1, 2])

        assert len(result_pubkey) == 33
        assert len(result_chain) == 32

    def test_derive_empty_levels_returns_same(self):
        _, chain_code, key_data, _, _ = decode_extended_key(VALID_BTC_XPUB)
        pubkey = key_data[1:] if key_data[0] == 0x00 else key_data

        result_pubkey, result_chain = derive_path_levels(pubkey, chain_code, [])

        assert result_pubkey == pubkey
        assert result_chain == chain_code


class TestPurposeByScriptTypeMapping:
    def test_all_script_types_have_purpose(self):
        for script_type in ScriptType:
            assert script_type in PURPOSE_BY_SCRIPT_TYPE


class TestNetworkConfigsMapping:
    def test_all_networks_have_config(self):
        for network in CoinType:
            assert network in NETWORK_CONFIGS


class TestKeyPrefixPatterns:
    def test_xpub_pattern(self):
        script_type, network = KEY_PREFIX_PATTERNS["xpub"]
        assert script_type == ScriptType.P2PKH
        assert network == CoinType.BITCOIN

    def test_ypub_pattern(self):
        script_type, network = KEY_PREFIX_PATTERNS["ypub"]
        assert script_type == ScriptType.P2SH_P2WPKH
        assert network == CoinType.BITCOIN

    def test_zpub_pattern(self):
        script_type, network = KEY_PREFIX_PATTERNS["zpub"]
        assert script_type == ScriptType.P2WPKH
        assert network is None

    def test_ltub_pattern(self):
        script_type, network = KEY_PREFIX_PATTERNS["Ltub"]
        assert script_type == ScriptType.P2PKH
        assert network == CoinType.LITECOIN

    def test_mtub_pattern(self):
        script_type, network = KEY_PREFIX_PATTERNS["Mtub"]
        assert script_type == ScriptType.P2SH_P2WPKH
        assert network == CoinType.LITECOIN


class TestGetKeyPrefix:
    def test_xpub_prefix(self):
        assert get_key_prefix(VALID_BTC_XPUB) == "xpub"

    def test_ypub_prefix(self):
        assert get_key_prefix(VALID_BTC_YPUB) == "ypub"

    def test_zpub_prefix(self):
        assert get_key_prefix(VALID_BTC_ZPUB) == "zpub"

    def test_unknown_prefix_returns_none(self):
        assert get_key_prefix("invalid_key") is None


class TestGetExtendedKeyInfo:
    def test_xpub_info(self):
        info = get_extended_key_info(VALID_BTC_XPUB)
        assert info is not None
        prefix, script_type, network = info
        assert prefix == "xpub"
        assert script_type == ScriptType.P2PKH
        assert network == CoinType.BITCOIN

    def test_ypub_info(self):
        info = get_extended_key_info(VALID_BTC_YPUB)
        assert info is not None
        prefix, script_type, network = info
        assert prefix == "ypub"
        assert script_type == ScriptType.P2SH_P2WPKH
        assert network == CoinType.BITCOIN

    def test_zpub_info(self):
        info = get_extended_key_info(VALID_BTC_ZPUB)
        assert info is not None
        prefix, script_type, network = info
        assert prefix == "zpub"
        assert script_type == ScriptType.P2WPKH
        assert network is None

    def test_unknown_key_returns_none(self):
        assert get_extended_key_info("invalid_key") is None


class TestNetworkConfigStruct:
    def test_btc_network_config(self):
        config = NETWORK_CONFIGS[CoinType.BITCOIN]
        assert config.p2pkh_prefix == b"\x00"
        assert config.p2sh_prefix == b"\x05"
        assert config.bech32_hrp == "bc"
        assert config.coin_type == 0

    def test_ltc_network_config(self):
        config = NETWORK_CONFIGS[CoinType.LITECOIN]
        assert config.p2pkh_prefix == b"\x30"
        assert config.p2sh_prefix == b"\x32"
        assert config.bech32_hrp == "ltc"
        assert config.coin_type == 2


class TestNeedsHardenedDerivation:
    def test_zpub_depth_0_does_not_need_hardened(self):
        assert needs_hardened_derivation(VALID_BTC_ZPUB, 0) is False

    def test_zpub_depth_1_does_not_need_hardened(self):
        assert needs_hardened_derivation(VALID_ELECTRUM_ZPUB, 1) is False

    def test_zpub_depth_3_does_not_need_hardened(self):
        assert needs_hardened_derivation(VALID_BTC_ZPUB, 3) is False

    def test_ypub_depth_1_does_not_need_hardened(self):
        assert needs_hardened_derivation(VALID_BTC_YPUB, 1) is False

    def test_xpub_depth_0_needs_hardened(self):
        assert needs_hardened_derivation(VALID_BTC_XPUB, 0) is True

    def test_xpub_depth_1_needs_hardened(self):
        assert needs_hardened_derivation(VALID_BTC_XPUB, 1) is True

    def test_xpub_depth_3_does_not_need_hardened(self):
        assert needs_hardened_derivation(VALID_BTC_XPUB, 3) is False

    def test_ltub_depth_1_needs_hardened(self):
        ltub = "Ltub2SSUS19CirucVPBSjuRMt2SF9H93viG9rz4TkpzAEFjsxHXKjA3jFe1b91cgf2f5dVLrjjJDBTQaVQHMJvhPLiTFGZqPXBbPNxae12HPLLN"
        assert needs_hardened_derivation(ltub, 1) is True


class TestBuildDerivationPathByDepth:
    def test_depth_0_with_hardened_derives_all_levels(self):
        levels, base_path = build_derivation_path(
            depth=0,
            script_type=ScriptType.P2WPKH,
            network=CoinType.BITCOIN,
            account=0,
            derive_hardened=True,
        )
        assert levels == [84, 0, 0]
        assert base_path == "m/84'/0'/0'"

    def test_depth_1_with_hardened_derives_coin_type_and_account(self):
        levels, base_path = build_derivation_path(
            depth=1,
            script_type=ScriptType.P2WPKH,
            network=CoinType.BITCOIN,
            account=0,
            derive_hardened=True,
        )
        assert levels == [0, 0]
        assert base_path == "m/84'/0'/0'"

    def test_depth_2_with_hardened_derives_only_account(self):
        levels, base_path = build_derivation_path(
            depth=2,
            script_type=ScriptType.P2WPKH,
            network=CoinType.BITCOIN,
            account=0,
            derive_hardened=True,
        )
        assert levels == [0]
        assert base_path == "m/84'/0'/0'"

    def test_depth_3_with_hardened_no_more_levels(self):
        levels, base_path = build_derivation_path(
            depth=3,
            script_type=ScriptType.P2WPKH,
            network=CoinType.BITCOIN,
            account=0,
            derive_hardened=True,
        )
        assert levels == []
        assert base_path == "m/84'/0'/0'"

    def test_without_hardened_returns_empty_levels_with_full_base_path(self):
        levels, base_path = build_derivation_path(
            depth=1,
            script_type=ScriptType.P2WPKH,
            network=CoinType.BITCOIN,
            account=0,
            derive_hardened=False,
        )
        assert levels == []
        assert base_path == "m/84'/0'/0'"

    def test_custom_account_included_in_levels(self):
        levels, base_path = build_derivation_path(
            depth=0,
            script_type=ScriptType.P2PKH,
            network=CoinType.BITCOIN,
            account=5,
            derive_hardened=True,
        )
        assert levels == [44, 0, 5]
        assert base_path == "m/44'/0'/5'"

    def test_litecoin_uses_correct_coin_type(self):
        levels, base_path = build_derivation_path(
            depth=0,
            script_type=ScriptType.P2PKH,
            network=CoinType.LITECOIN,
            account=0,
            derive_hardened=True,
        )
        assert levels == [44, 2, 0]
        assert base_path == "m/44'/2'/0'"


class TestDerivationByKeyDepth:
    def test_key_at_depth_1_derives_with_full_base_path(self):
        addresses, base_path = derive_addresses(
            VALID_ELECTRUM_ZPUB,
            network=CoinType.BITCOIN,
            script_type=ScriptType.P2WPKH,
            change=0,
            start_index=0,
            count=3,
        )

        assert base_path == "m/84'/0'/0'"
        assert len(addresses) == 3
        for addr in addresses:
            assert addr.address.startswith("bc1q")

    def test_key_at_depth_1_first_receiving_address_path(self):
        addresses, _ = derive_addresses(
            VALID_ELECTRUM_ZPUB,
            network=CoinType.BITCOIN,
            script_type=ScriptType.P2WPKH,
            change=0,
            start_index=0,
            count=1,
        )

        assert addresses[0].path == "m/84'/0'/0'/0/0"
        assert addresses[0].change == 0
        assert addresses[0].index == 0

    def test_key_at_depth_1_first_change_address_path(self):
        addresses, _ = derive_addresses(
            VALID_ELECTRUM_ZPUB,
            network=CoinType.BITCOIN,
            script_type=ScriptType.P2WPKH,
            change=1,
            start_index=0,
            count=1,
        )

        assert addresses[0].path == "m/84'/0'/0'/1/0"
        assert addresses[0].change == 1

    def test_key_at_depth_3_uses_full_base_path(self):
        addresses, base_path = derive_addresses(
            VALID_BTC_ZPUB,
            network=CoinType.BITCOIN,
            script_type=ScriptType.P2WPKH,
            change=0,
            start_index=0,
            count=3,
        )

        assert base_path == "m/84'/0'/0'"
        assert len(addresses) == 3

    def test_key_at_depth_0_builds_full_path(self):
        addresses, base_path = derive_addresses(
            VALID_BTC_XPUB,
            network=CoinType.BITCOIN,
            script_type=ScriptType.P2PKH,
            change=0,
            start_index=0,
            count=2,
        )

        assert "44'" in base_path
        assert "0'" in base_path
        assert len(addresses) == 2
