const KNOWN_ISSUER_ICONS: Record<string, string> = {
  Allianz: "allianz",
  Amundi: "amundi",
  Andbank: "andbank",
  Ark: "ark",
  AXA: "axa",
  BBVA: "bbva",
  BlackRock: "blackrock",
  "BNP Paribas": "bnpparibas",
  Caser: "caser",
  CBNK: "cbnk",
  DWS: "dws",
  Fidelity: "fidelity",
  "Franklin Templeton": "franklintempleton",
  "Global X": "globalx",
  Goldman: "goldman",
  HANetf: "hanetf",
  HSBC: "hsbc",
  ING: "ing",
  Invesco: "invesco",
  "JP Morgan": "jpmorgan",
  "Legal & General": "legalgeneral",
  "Morgan Stanley": "morganstanley",
  MyInvestor: "myinvestor",
  PIMCO: "pimco",
  SPDR: "spdr",
  UBS: "ubs",
  VanEck: "vaneck",
  Vanguard: "vanguard",
  WisdomTree: "wisdomtree",
  Xtrackers: "xtrackers",
}

export function getIssuerIconPath(
  issuer: string | null | undefined,
): string | null {
  if (!issuer) return null
  const iconName = KNOWN_ISSUER_ICONS[issuer]
  if (!iconName) return null
  return `/icons/issuers/${iconName}.png`
}
