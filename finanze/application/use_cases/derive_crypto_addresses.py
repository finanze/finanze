from uuid import UUID

from application.ports.entity_port import EntityPort
from application.ports.public_key_derivation import PublicKeyDerivation
from domain import native_entities
from domain.entity import EntityType
from domain.exception.exceptions import EntityNotFound
from domain.public_key import (
    AddressDerivationRequest,
    AddressDerivationPreviewRequest,
    DerivedAddressesResult,
    CoinType,
)
from domain.use_cases.derive_crypto_addresses import DeriveCryptoAddresses

ENTITY_TO_COIN_TYPE = {
    native_entities.BITCOIN.id: CoinType.BITCOIN,
    native_entities.LITECOIN.id: CoinType.LITECOIN,
}


def get_coin_type_from_entity_id(entity_id: UUID) -> CoinType:
    if entity_id not in ENTITY_TO_COIN_TYPE:
        entity = native_entities.get_native_by_id(entity_id, EntityType.CRYPTO_WALLET)
        if not entity:
            raise EntityNotFound(str(entity_id))
        raise ValueError(f"Entity {entity.name} does not support address derivation")

    return ENTITY_TO_COIN_TYPE[entity_id]


class DeriveCryptoAddressesImpl(DeriveCryptoAddresses):
    def __init__(
        self,
        public_key_derivation: PublicKeyDerivation,
        entity_port: EntityPort,
    ):
        self._public_key_derivation = public_key_derivation
        self._entity_port = entity_port

    @staticmethod
    def _get_coin_type_from_entity_id(entity_id: UUID) -> CoinType:
        return get_coin_type_from_entity_id(entity_id)

    async def execute(
        self,
        request: AddressDerivationPreviewRequest,
    ) -> DerivedAddressesResult:
        coin_type = get_coin_type_from_entity_id(request.entity.id)

        derivation_request = AddressDerivationRequest(
            xpub=request.xpub,
            coin=coin_type,
            receiving_range=(0, request.range),
            change_range=(0, request.range),
            script_type=request.script_type,
        )

        return self._public_key_derivation.calculate(derivation_request)
