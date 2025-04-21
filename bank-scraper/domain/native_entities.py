from typing import Optional
from uuid import UUID

from domain.financial_entity import NativeFinancialEntity, Feature, PinDetails, CredentialType

MY_INVESTOR = NativeFinancialEntity(
    id=UUID("e0000000-0000-0000-0000-000000000001"),
    name="MyInvestor",
    features=[Feature.POSITION, Feature.AUTO_CONTRIBUTIONS, Feature.TRANSACTIONS],
    credentials_template={
        "user": CredentialType.ID,
        "password": CredentialType.PASSWORD
    }
)

UNICAJA = NativeFinancialEntity(
    id=UUID("e0000000-0000-0000-0000-000000000002"),
    name="Unicaja",
    features=[Feature.POSITION],
    credentials_template={
        "user": CredentialType.ID,
        "password": CredentialType.PASSWORD
    }
)

TRADE_REPUBLIC = NativeFinancialEntity(
    id=UUID("e0000000-0000-0000-0000-000000000003"),
    name="Trade Republic",
    features=[Feature.POSITION, Feature.TRANSACTIONS, Feature.AUTO_CONTRIBUTIONS],
    pin=PinDetails(positions=4),
    credentials_template={
        "phone": CredentialType.PHONE,
        "password": CredentialType.PIN,
    }
)

URBANITAE = NativeFinancialEntity(
    id=UUID("e0000000-0000-0000-0000-000000000004"),
    name="Urbanitae",
    features=[Feature.POSITION, Feature.TRANSACTIONS, Feature.HISTORIC],
    credentials_template={
        "user": CredentialType.EMAIL,
        "password": CredentialType.PASSWORD
    }
)

WECITY = NativeFinancialEntity(
    id=UUID("e0000000-0000-0000-0000-000000000005"),
    name="Wecity",
    features=[Feature.POSITION, Feature.TRANSACTIONS, Feature.HISTORIC],
    pin=PinDetails(positions=6),
    credentials_template={
        "user": CredentialType.EMAIL,
        "password": CredentialType.PASSWORD
    }
)

SEGO = NativeFinancialEntity(
    id=UUID("e0000000-0000-0000-0000-000000000006"),
    name="SEGO",
    features=[Feature.POSITION, Feature.TRANSACTIONS, Feature.HISTORIC],
    pin=PinDetails(positions=6),
    credentials_template={
        "user": CredentialType.EMAIL,
        "password": CredentialType.PASSWORD
    }
)

MINTOS = NativeFinancialEntity(
    id=UUID("e0000000-0000-0000-0000-000000000007"),
    name="Mintos",
    features=[Feature.POSITION],
    credentials_template={
        "user": CredentialType.EMAIL,
        "password": CredentialType.PASSWORD
    }
)

F24 = NativeFinancialEntity(
    id=UUID("e0000000-0000-0000-0000-000000000008"),
    name="Freedom24",
    features=[Feature.POSITION],
    credentials_template={
        "user": CredentialType.EMAIL,
        "password": CredentialType.PASSWORD
    }
)

NATIVE_ENTITIES = [
    MY_INVESTOR,
    UNICAJA,
    TRADE_REPUBLIC,
    URBANITAE,
    WECITY,
    SEGO,
    MINTOS,
    F24
]


def get_native_by_id(entity_id: UUID) -> Optional[NativeFinancialEntity]:
    return next((e for e in NATIVE_ENTITIES if entity_id == e.id), None)
