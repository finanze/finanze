from typing import Optional
from uuid import UUID

from domain.financial_entity import (
    NativeFinancialEntity,
    Feature,
    PinDetails,
    CredentialType,
    EntitySetupLoginType,
)

MY_INVESTOR = NativeFinancialEntity(
    id=UUID("e0000000-0000-0000-0000-000000000001"),
    name="MyInvestor",
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
    is_real=True,
    features=[Feature.POSITION],
    setup_login_type=EntitySetupLoginType.AUTOMATED,
    credentials_template={"token": CredentialType.API_TOKEN},
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
]


def get_native_by_id(entity_id: UUID) -> Optional[NativeFinancialEntity]:
    return next((e for e in NATIVE_ENTITIES if entity_id == e.id), None)
