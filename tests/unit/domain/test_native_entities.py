from domain.entity import EntityType
from domain.external_integration import ExternalIntegrationId
from domain.native_entities import NATIVE_ENTITIES, ZERION, get_native_by_id


def test_zerion_is_registered_as_a_native_crypto_wallet_entity():
    assert ZERION in NATIVE_ENTITIES
    assert ZERION.type == EntityType.CRYPTO_WALLET
    assert ZERION.required_external_integrations == [ExternalIntegrationId.ZERION]
    assert ZERION.allows_hd_wallet is False


def test_get_native_by_id_resolves_zerion():
    assert get_native_by_id(ZERION.id, EntityType.CRYPTO_WALLET) is ZERION
