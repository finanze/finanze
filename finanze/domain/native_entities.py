from typing import Optional
from uuid import UUID

from domain.entity import (
    CredentialType,
    Entity,
    EntitySetupLoginType,
    EntityType,
    Feature,
    NativeCryptoWalletEntity,
    NativeFinancialEntity,
    PinDetails,
)

MY_INVESTOR = NativeFinancialEntity(
    id=UUID("e0000000-0000-0000-0000-000000000001"),
    name="MyInvestor",
    type=EntityType.FINANCIAL_INSTITUTION,
    is_real=True,
    features=[Feature.POSITION, Feature.AUTO_CONTRIBUTIONS, Feature.TRANSACTIONS],
    setup_login_type=EntitySetupLoginType.AUTOMATED,
    pin=PinDetails(positions=6),
    credentials_template={
        "user": CredentialType.ID,
        "password": CredentialType.PASSWORD,
    },
)

UNICAJA = NativeFinancialEntity(
    id=UUID("e0000000-0000-0000-0000-000000000002"),
    name="Unicaja",
    type=EntityType.FINANCIAL_INSTITUTION,
    is_real=True,
    features=[Feature.POSITION],
    setup_login_type=EntitySetupLoginType.MANUAL,
    credentials_template={
        "user": CredentialType.ID,
        "password": CredentialType.PASSWORD,
        "abck": CredentialType.INTERNAL,
    },
)

TRADE_REPUBLIC = NativeFinancialEntity(
    id=UUID("e0000000-0000-0000-0000-000000000003"),
    name="Trade Republic",
    type=EntityType.FINANCIAL_INSTITUTION,
    is_real=True,
    features=[Feature.POSITION, Feature.TRANSACTIONS, Feature.AUTO_CONTRIBUTIONS],
    setup_login_type=EntitySetupLoginType.AUTOMATED,
    pin=PinDetails(positions=4),
    credentials_template={
        "phone": CredentialType.PHONE,
        "password": CredentialType.PIN,
    },
)

URBANITAE = NativeFinancialEntity(
    id=UUID("e0000000-0000-0000-0000-000000000004"),
    name="Urbanitae",
    type=EntityType.FINANCIAL_INSTITUTION,
    is_real=True,
    features=[Feature.POSITION, Feature.TRANSACTIONS, Feature.HISTORIC],
    setup_login_type=EntitySetupLoginType.AUTOMATED,
    credentials_template={
        "user": CredentialType.EMAIL,
        "password": CredentialType.PASSWORD,
    },
)

WECITY = NativeFinancialEntity(
    id=UUID("e0000000-0000-0000-0000-000000000005"),
    name="Wecity",
    type=EntityType.FINANCIAL_INSTITUTION,
    is_real=True,
    features=[Feature.POSITION, Feature.TRANSACTIONS, Feature.HISTORIC],
    setup_login_type=EntitySetupLoginType.AUTOMATED,
    pin=PinDetails(positions=6),
    credentials_template={
        "user": CredentialType.EMAIL,
        "password": CredentialType.PASSWORD,
    },
)

SEGO = NativeFinancialEntity(
    id=UUID("e0000000-0000-0000-0000-000000000006"),
    name="SEGO",
    type=EntityType.FINANCIAL_INSTITUTION,
    is_real=True,
    features=[Feature.POSITION, Feature.TRANSACTIONS, Feature.HISTORIC],
    setup_login_type=EntitySetupLoginType.AUTOMATED,
    pin=PinDetails(positions=6),
    credentials_template={
        "user": CredentialType.EMAIL,
        "password": CredentialType.PASSWORD,
    },
)

MINTOS = NativeFinancialEntity(
    id=UUID("e0000000-0000-0000-0000-000000000007"),
    name="Mintos",
    type=EntityType.FINANCIAL_INSTITUTION,
    is_real=True,
    features=[Feature.POSITION],
    setup_login_type=EntitySetupLoginType.MANUAL,
    credentials_template={
        "user": CredentialType.EMAIL,
        "password": CredentialType.PASSWORD,
        "cookie": CredentialType.INTERNAL_TEMP,
    },
)

F24 = NativeFinancialEntity(
    id=UUID("e0000000-0000-0000-0000-000000000008"),
    name="Freedom24",
    type=EntityType.FINANCIAL_INSTITUTION,
    is_real=True,
    features=[Feature.POSITION, Feature.TRANSACTIONS],
    setup_login_type=EntitySetupLoginType.AUTOMATED,
    credentials_template={
        "user": CredentialType.EMAIL,
        "password": CredentialType.PASSWORD,
    },
)

INDEXA_CAPITAL = NativeFinancialEntity(
    id=UUID("e0000000-0000-0000-0000-000000000009"),
    name="Indexa Capital",
    type=EntityType.FINANCIAL_INSTITUTION,
    is_real=True,
    features=[Feature.POSITION],
    setup_login_type=EntitySetupLoginType.AUTOMATED,
    credentials_template={"token": CredentialType.API_TOKEN},
)


def _create_crypto_entity(
    num: int, name: str, features: list[Feature] = [Feature.POSITION]
) -> NativeCryptoWalletEntity:
    return NativeCryptoWalletEntity(
        id=UUID(f"c0000000-0000-0000-0000-000000000{num:03d}"),
        name=name,
        type=EntityType.CRYPTO_WALLET,
        is_real=True,
        features=features,
    )


BITCOIN = _create_crypto_entity(1, "Bitcoin")
ETHEREUM = _create_crypto_entity(2, "Ethereum")
LITECOIN = _create_crypto_entity(3, "Litecoin")
TRON = _create_crypto_entity(4, "Tron")

COMMODITIES = Entity(
    id=UUID("ccccdddd-0000-0000-0000-000000000000"),
    name="Commodity Source",
    type=EntityType.COMMODITY,
    is_real=True,
)

NATIVE_ENTITIES = [
    MY_INVESTOR,
    UNICAJA,
    TRADE_REPUBLIC,
    URBANITAE,
    WECITY,
    SEGO,
    MINTOS,
    F24,
    INDEXA_CAPITAL,
    BITCOIN,
    ETHEREUM,
    LITECOIN,
    TRON,
    COMMODITIES,
]


def get_native_by_id(
    entity_id: UUID, entity_type: EntityType
) -> Optional[NativeFinancialEntity | NativeCryptoWalletEntity]:
    return next(
        (e for e in NATIVE_ENTITIES if entity_id == e.id and entity_type == e.type),
        None,
    )
