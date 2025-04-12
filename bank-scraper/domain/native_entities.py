from uuid import UUID

from domain.financial_entity import FinancialEntity, Feature, PinDetails

MY_INVESTOR = FinancialEntity(
    id=UUID("e0000000-0000-0000-0000-000000000001"),
    name="MyInvestor",
    features=[Feature.POSITION, Feature.AUTO_CONTRIBUTIONS, Feature.TRANSACTIONS],
)
UNICAJA = FinancialEntity(
    id=UUID("e0000000-0000-0000-0000-000000000002"),
    name="Unicaja",
    features=[Feature.POSITION],
)
TRADE_REPUBLIC = FinancialEntity(
    id=UUID("e0000000-0000-0000-0000-000000000003"),
    name="Trade Republic",
    features=[Feature.POSITION, Feature.TRANSACTIONS],
    pin=PinDetails(positions=4),
)
URBANITAE = FinancialEntity(
    id=UUID("e0000000-0000-0000-0000-000000000004"),
    name="Urbanitae",
    features=[Feature.POSITION, Feature.TRANSACTIONS, Feature.HISTORIC],
)
WECITY = FinancialEntity(
    id=UUID("e0000000-0000-0000-0000-000000000005"),
    name="Wecity",
    features=[Feature.POSITION, Feature.TRANSACTIONS, Feature.HISTORIC],
    pin=PinDetails(positions=6),
)
SEGO = FinancialEntity(
    id=UUID("e0000000-0000-0000-0000-000000000006"),
    name="SEGO",
    features=[Feature.POSITION, Feature.TRANSACTIONS, Feature.HISTORIC],
    pin=PinDetails(positions=6),
)
MINTOS = FinancialEntity(
    id=UUID("e0000000-0000-0000-0000-000000000007"),
    name="Mintos",
    features=[Feature.POSITION],
)
F24 = FinancialEntity(
    id=UUID("e0000000-0000-0000-0000-000000000008"),
    name="Freedom24",
    features=[Feature.POSITION],
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
