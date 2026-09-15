from enum import Enum
from typing import Optional


class KnownIssuer(str, Enum):
    TWENTY_ONE_SHARES = "21Shares"
    ALLIANZ = "Allianz"
    AMUNDI = "Amundi"
    ANDBANK = "Andbank"
    APOLLO = "Apollo"
    ARK = "Ark"
    AXA = "AXA"
    BBVA = "BBVA"
    BITWISE = "Bitwise"
    BLACKROCK = "BlackRock"
    BNP_PARIBAS = "BNP Paribas"
    CASER = "Caser"
    CBNK = "CBNK"
    COINSHARES = "CoinShares"
    CRESCENTA = "Crescenta"
    DDA = "DDA"
    DWS = "DWS"
    EQT = "EQT"
    FIDELITY = "Fidelity"
    FIRST_TRUST = "First Trust"
    FRANKLIN_TEMPLETON = "Franklin Templeton"
    GENERALI = "Generali"
    GLOBAL_X = "Global X"
    GOLDMAN = "Goldman"
    GRANITESHARES = "GraniteShares"
    HANETF = "HANetf"
    HSBC = "HSBC"
    ING = "ING"
    INVESCO = "Invesco"
    JP_MORGAN = "JP Morgan"
    KRANESHARES = "KraneShares"
    LEGAL_GENERAL = "Legal & General"
    LEVERAGE_SHARES = "Leverage Shares"
    MORGAN_STANLEY = "Morgan Stanley"
    MY_INVESTOR = "MyInvestor"
    PIMCO = "PIMCO"
    ROBECO = "Robeco"
    SPROTT = "Sprott"
    STATE_STREET = "State Street"
    UBS = "UBS"
    VANECK = "VanEck"
    VANGUARD = "Vanguard"
    VONTOBEL = "Vontobel"
    WISDOMTREE = "WisdomTree"
    XTRACKERS = "Xtrackers"

    @property
    def compact(self) -> str:
        return self.value.replace(" ", "").replace("&", "").lower()


_MANUAL_ALIASES: dict[str, KnownIssuer] = {
    "ishrs ": KnownIssuer.BLACKROCK,
    "ishares": KnownIssuer.BLACKROCK,
    "is ": KnownIssuer.BLACKROCK,
    "bgf ": KnownIssuer.BLACKROCK,
    "jpm ": KnownIssuer.JP_MORGAN,
    "dbx ": KnownIssuer.XTRACKERS,
    "franklin ": KnownIssuer.FRANKLIN_TEMPLETON,
    "templeton ": KnownIssuer.FRANKLIN_TEMPLETON,
    "spdr": KnownIssuer.STATE_STREET,
    "ssga ": KnownIssuer.STATE_STREET,
    "lyxor": KnownIssuer.AMUNDI,
    "sycomore": KnownIssuer.GENERALI,
    "incomeshares": KnownIssuer.LEVERAGE_SHARES,
    "income shares": KnownIssuer.LEVERAGE_SHARES,
    "deutsche digital assets": KnownIssuer.DDA,
    "l&g ": KnownIssuer.LEGAL_GENERAL,
}

_ISSUER_ALIASES: dict[str, KnownIssuer] = {
    **{issuer.value.lower(): issuer for issuer in KnownIssuer},
    **{issuer.compact: issuer for issuer in KnownIssuer},
    **_MANUAL_ALIASES,
}


def _match_issuer(text: str) -> Optional[KnownIssuer]:
    cleaned = text.strip().lower()
    for alias, issuer in _ISSUER_ALIASES.items():
        if cleaned.startswith(alias):
            return issuer
    return None


def resolve_issuer(issuer: Optional[str], *fallback_sources: str) -> Optional[str]:
    if issuer is not None:
        match = _match_issuer(issuer)
        return match.value if match is not None else issuer.strip()
    for source in fallback_sources:
        match = _match_issuer(source)
        if match is not None:
            return match.value
    return None
