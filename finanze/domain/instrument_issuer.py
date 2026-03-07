from enum import Enum
from typing import Optional


class KnownIssuer(str, Enum):
    ALLIANZ = "Allianz"
    AMUNDI = "Amundi"
    ANDBANK = "Andbank"
    ARK = "Ark"
    AXA = "AXA"
    BBVA = "BBVA"
    BLACKROCK = "BlackRock"
    BNP_PARIBAS = "BNP Paribas"
    CASER = "Caser"
    CBNK = "CBNK"
    DWS = "DWS"
    FIDELITY = "Fidelity"
    FRANKLIN_TEMPLETON = "Franklin Templeton"
    GLOBAL_X = "Global X"
    GOLDMAN = "Goldman"
    HANETF = "HANetf"
    HSBC = "HSBC"
    ING = "ING"
    INVESCO = "Invesco"
    JP_MORGAN = "JP Morgan"
    LEGAL_GENERAL = "Legal & General"
    MORGAN_STANLEY = "Morgan Stanley"
    MY_INVESTOR = "MyInvestor"
    PIMCO = "PIMCO"
    SPDR = "SPDR"
    UBS = "UBS"
    VANECK = "VanEck"
    VANGUARD = "Vanguard"
    WISDOMTREE = "WisdomTree"
    XTRACKERS = "Xtrackers"

    def compact(self) -> str:
        return self.value.replace(" ", "").replace("&", "").lower()


_MANUAL_ALIASES: dict[str, KnownIssuer] = {
    "ishrs ": KnownIssuer.BLACKROCK,
    "ishares ": KnownIssuer.BLACKROCK,
    "is ": KnownIssuer.BLACKROCK,
    "bgf ": KnownIssuer.BLACKROCK,
    "jpm ": KnownIssuer.JP_MORGAN,
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
