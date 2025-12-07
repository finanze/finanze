from typing import Optional
from uuid import UUID

from domain.entity import (
    Entity,
    EntityOrigin,
    EntityType,
    Feature,
)
from domain.native_entity import (
    PinDetails,
    CredentialType,
    EntitySetupLoginType,
    EntitySessionCategory,
    NativeFinancialEntity,
    NativeCryptoWalletEntity,
)
from domain.external_integration import ExternalIntegrationId
from domain.global_position import ProductType

MY_INVESTOR = NativeFinancialEntity(
    id=UUID("e0000000-0000-0000-0000-000000000001"),
    name="MyInvestor",
    natural_id="BACAESMM",
    type=EntityType.FINANCIAL_INSTITUTION,
    origin=EntityOrigin.NATIVE,
    features=[Feature.POSITION, Feature.AUTO_CONTRIBUTIONS, Feature.TRANSACTIONS],
    products=[
        ProductType.ACCOUNT,
        ProductType.CARD,
        ProductType.STOCK_ETF,
        ProductType.FUND,
        ProductType.FUND_PORTFOLIO,
        ProductType.DEPOSIT,
    ],
    setup_login_type=EntitySetupLoginType.AUTOMATED,
    session_category=EntitySessionCategory.UNDEFINED,
    pin=PinDetails(positions=6),
    credentials_template={
        "user": CredentialType.ID,
        "password": CredentialType.PASSWORD,
    },
)

UNICAJA = NativeFinancialEntity(
    id=UUID("e0000000-0000-0000-0000-000000000002"),
    name="Unicaja",
    natural_id="UCJAES2M",
    type=EntityType.FINANCIAL_INSTITUTION,
    origin=EntityOrigin.NATIVE,
    features=[Feature.POSITION, Feature.AUTO_CONTRIBUTIONS],
    products=[ProductType.ACCOUNT, ProductType.CARD, ProductType.LOAN],
    setup_login_type=EntitySetupLoginType.MANUAL,
    session_category=EntitySessionCategory.UNDEFINED,
    credentials_template={
        "user": CredentialType.ID,
        "password": CredentialType.PASSWORD,
        "abck": CredentialType.INTERNAL,
    },
)

TRADE_REPUBLIC = NativeFinancialEntity(
    id=UUID("e0000000-0000-0000-0000-000000000003"),
    name="Trade Republic",
    natural_id="TRBKDEBB",
    type=EntityType.FINANCIAL_INSTITUTION,
    origin=EntityOrigin.NATIVE,
    features=[Feature.POSITION, Feature.TRANSACTIONS, Feature.AUTO_CONTRIBUTIONS],
    products=[
        ProductType.ACCOUNT,
        ProductType.STOCK_ETF,
        ProductType.FUND,
        ProductType.CRYPTO,
    ],
    setup_login_type=EntitySetupLoginType.AUTOMATED,
    session_category=EntitySessionCategory.SHORT,
    pin=PinDetails(positions=4),
    credentials_template={
        "phone": CredentialType.PHONE,
        "password": CredentialType.PIN,
    },
)

URBANITAE = NativeFinancialEntity(
    id=UUID("e0000000-0000-0000-0000-000000000004"),
    name="Urbanitae",
    natural_id=None,
    type=EntityType.FINANCIAL_INSTITUTION,
    origin=EntityOrigin.NATIVE,
    features=[Feature.POSITION, Feature.TRANSACTIONS, Feature.HISTORIC],
    products=[ProductType.ACCOUNT, ProductType.REAL_ESTATE_CF],
    setup_login_type=EntitySetupLoginType.AUTOMATED,
    session_category=EntitySessionCategory.UNDEFINED,
    credentials_template={
        "user": CredentialType.EMAIL,
        "password": CredentialType.PASSWORD,
    },
)

WECITY = NativeFinancialEntity(
    id=UUID("e0000000-0000-0000-0000-000000000005"),
    name="Wecity",
    natural_id=None,
    type=EntityType.FINANCIAL_INSTITUTION,
    origin=EntityOrigin.NATIVE,
    features=[Feature.POSITION, Feature.TRANSACTIONS, Feature.HISTORIC],
    products=[ProductType.ACCOUNT, ProductType.REAL_ESTATE_CF],
    setup_login_type=EntitySetupLoginType.AUTOMATED,
    session_category=EntitySessionCategory.MEDIUM,
    pin=PinDetails(positions=6),
    credentials_template={
        "user": CredentialType.EMAIL,
        "password": CredentialType.PASSWORD,
    },
)

SEGO = NativeFinancialEntity(
    id=UUID("e0000000-0000-0000-0000-000000000006"),
    name="SEGO",
    natural_id=None,
    type=EntityType.FINANCIAL_INSTITUTION,
    origin=EntityOrigin.NATIVE,
    features=[Feature.POSITION, Feature.TRANSACTIONS, Feature.HISTORIC],
    products=[ProductType.ACCOUNT, ProductType.FACTORING],
    setup_login_type=EntitySetupLoginType.AUTOMATED,
    session_category=EntitySessionCategory.MEDIUM,
    pin=PinDetails(positions=6),
    credentials_template={
        "user": CredentialType.EMAIL,
        "password": CredentialType.PASSWORD,
    },
)

MINTOS = NativeFinancialEntity(
    id=UUID("e0000000-0000-0000-0000-000000000007"),
    name="Mintos",
    natural_id=None,
    type=EntityType.FINANCIAL_INSTITUTION,
    origin=EntityOrigin.NATIVE,
    features=[Feature.POSITION],
    products=[ProductType.ACCOUNT, ProductType.CROWDLENDING],
    setup_login_type=EntitySetupLoginType.MANUAL,
    session_category=EntitySessionCategory.NONE,
    credentials_template={
        "user": CredentialType.EMAIL,
        "password": CredentialType.PASSWORD,
        "cookie": CredentialType.INTERNAL_TEMP,
    },
)

F24 = NativeFinancialEntity(
    id=UUID("e0000000-0000-0000-0000-000000000008"),
    name="Freedom24",
    natural_id=None,
    type=EntityType.FINANCIAL_INSTITUTION,
    origin=EntityOrigin.NATIVE,
    features=[Feature.POSITION, Feature.TRANSACTIONS],
    products=[ProductType.ACCOUNT, ProductType.DEPOSIT],
    setup_login_type=EntitySetupLoginType.AUTOMATED,
    session_category=EntitySessionCategory.UNDEFINED,
    credentials_template={
        "user": CredentialType.EMAIL,
        "password": CredentialType.PASSWORD,
    },
)

INDEXA_CAPITAL = NativeFinancialEntity(
    id=UUID("e0000000-0000-0000-0000-000000000009"),
    name="Indexa Capital",
    natural_id=None,
    type=EntityType.FINANCIAL_INSTITUTION,
    origin=EntityOrigin.NATIVE,
    features=[Feature.POSITION, Feature.TRANSACTIONS],
    products=[ProductType.ACCOUNT, ProductType.FUND, ProductType.FUND_PORTFOLIO],
    setup_login_type=EntitySetupLoginType.AUTOMATED,
    session_category=EntitySessionCategory.UNDEFINED,
    credentials_template={"token": CredentialType.API_TOKEN},
)

ING = NativeFinancialEntity(
    id=UUID("e0000000-0000-0000-0000-000000000010"),
    name="ING",
    natural_id="INGDESMM",
    type=EntityType.FINANCIAL_INSTITUTION,
    origin=EntityOrigin.NATIVE,
    features=[Feature.POSITION, Feature.TRANSACTIONS, Feature.AUTO_CONTRIBUTIONS],
    products=[
        ProductType.ACCOUNT,
        ProductType.CARD,
        ProductType.STOCK_ETF,
        ProductType.FUND,
    ],
    setup_login_type=EntitySetupLoginType.MANUAL,
    session_category=EntitySessionCategory.NONE,
    credentials_template={
        "genomaCookie": CredentialType.INTERNAL_TEMP,
        "genomaSessionId": CredentialType.INTERNAL_TEMP,
        "apiCookie": CredentialType.INTERNAL_TEMP,
        "apiAuth": CredentialType.INTERNAL_TEMP,
        "apiExtendedSessionCtx": CredentialType.INTERNAL_TEMP,
    },
)

CAJAMAR = NativeFinancialEntity(
    id=UUID("e0000000-0000-0000-0000-000000000011"),
    name="Grupo Cajamar",
    natural_id="BCCAESMM",
    type=EntityType.FINANCIAL_INSTITUTION,
    origin=EntityOrigin.NATIVE,
    features=[Feature.POSITION],
    products=[ProductType.ACCOUNT, ProductType.CARD, ProductType.LOAN],
    setup_login_type=EntitySetupLoginType.AUTOMATED,
    session_category=EntitySessionCategory.UNDEFINED,
    credentials_template={
        "user": CredentialType.USER,
        "password": CredentialType.PASSWORD,
    },
)


def _create_crypto_entity(
    num: int,
    name: str,
    features: list[Feature] = [Feature.POSITION],
    required_external_integrations: list[ExternalIntegrationId] = [],
) -> NativeCryptoWalletEntity:
    return NativeCryptoWalletEntity(
        id=UUID(f"c0000000-0000-0000-0000-000000000{num:03d}"),
        name=name,
        natural_id=None,
        type=EntityType.CRYPTO_WALLET,
        origin=EntityOrigin.NATIVE,
        features=features,
        required_external_integrations=required_external_integrations,
    )


BITCOIN = _create_crypto_entity(1, "Bitcoin")
ETHEREUM = _create_crypto_entity(2, "Ethereum")
LITECOIN = _create_crypto_entity(3, "Litecoin")
TRON = _create_crypto_entity(4, "Tron")
BSC = _create_crypto_entity(
    5,
    "Binance Smart Chain",
)

COMMODITIES = Entity(
    id=UUID("ccccdddd-0000-0000-0000-000000000000"),
    name="Commodity Source",
    natural_id=None,
    type=EntityType.COMMODITY,
    origin=EntityOrigin.INTERNAL,
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
    ING,
    CAJAMAR,
    BITCOIN,
    ETHEREUM,
    LITECOIN,
    TRON,
    BSC,
    COMMODITIES,
]


def get_native_by_id(
    entity_id: UUID, *entity_types: EntityType
) -> Optional[NativeFinancialEntity | NativeCryptoWalletEntity]:
    return next(
        (e for e in NATIVE_ENTITIES if entity_id == e.id and e.type in entity_types),
        None,
    )
