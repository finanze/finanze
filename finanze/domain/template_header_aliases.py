import re
import unicodedata
from typing import Any, Optional

HEADER_STOPWORDS = frozenset(
    {
        "de",
        "del",
        "la",
        "el",
        "of",
        "the",
        "di",
        "della",
        "du",
        "des",
        "da",
        "do",
        "der",
        "die",
    }
)

HEADER_ALIASES: dict[str, tuple[str, ...]] = {
    "date": (
        "fecha operacion",
        "fecha contable",
        "fecha",
        "f operacion",
        "transaction date",
        "operation date",
        "booking date",
        "date",
        "data operazione",
        "data contabile",
        "data",
        "buchungsdatum",
        "buchungstag",
        "datum",
        "date operation",
        "date comptable",
        "data movimento",
        "data lancamento",
        "fecha valor",
        "f valor",
        "value date",
        "data valuta",
        "wertstellung",
        "date valeur",
        "data valor",
    ),
    "order_date": (
        "fecha orden",
        "order date",
        "data ordine",
        "auftragsdatum",
        "date ordre",
        "data ordem",
    ),
    "name": (
        "concepto",
        "descripcion",
        "description",
        "detalle",
        "concept",
        "nombre",
        "name",
        "descrizione",
        "causale",
        "verwendungszweck",
        "beschreibung",
        "buchungstext",
        "libelle",
        "descricao",
        "nome",
        "nom",
        "producto",
        "product",
        "instrumento",
        "instrument",
        "details",
    ),
    "amount": (
        "importe",
        "cantidad",
        "amount",
        "importo",
        "betrag",
        "umsatz",
        "montant",
        "valor",
        "monto",
        "total",
    ),
    "amount_in": (
        "entrada dinero",
        "importe entrada",
        "abono",
        "abonos",
        "haber",
        "ingreso",
        "ingresos",
        "credit",
        "credits",
        "money in",
        "paid in",
        "cash in",
        "inflow",
        "entrata",
        "entrate",
        "accredito",
        "gutschrift",
        "eingang",
        "entree",
    ),
    "amount_out": (
        "salida dinero",
        "importe salida",
        "cargo",
        "cargos",
        "debe",
        "adeudo",
        "adeudos",
        "debit",
        "debits",
        "money out",
        "paid out",
        "cash out",
        "outflow",
        "uscita",
        "uscite",
        "addebito",
        "lastschrift",
        "ausgang",
        "sortie",
    ),
    "net_amount": (
        "importe neto",
        "neto",
        "net amount",
        "net",
        "importo netto",
        "netto",
        "montant net",
        "valor liquido",
    ),
    "currency": (
        "divisa",
        "moneda",
        "currency",
        "ccy",
        "valuta",
        "wahrung",
        "devise",
        "moeda",
    ),
    "ref": (
        "referencia",
        "reference",
        "ref",
        "no mov",
        "nomov",
        "num mov",
        "numero movimiento",
        "no operacion",
        "numero operacion",
        "transaction id",
        "id transaccion",
        "id operacion",
        "id",
        "riferimento",
        "referenz",
        "referencia operacao",
    ),
    "type": (
        "tipo",
        "tipo movimiento",
        "tipo operacion",
        "type",
        "transaction type",
        "tipologia",
        "typ",
        "buchungsart",
        "tipo operazione",
    ),
    "counterparty": (
        "beneficiario",
        "ordenante",
        "contraparte",
        "counterparty",
        "payee",
        "payer",
        "beneficiary",
        "merchant",
        "comercio",
        "controparte",
        "empfanger",
        "auftraggeber",
        "beneficiaire",
    ),
    "iban": (
        "iban",
        "cuenta",
        "numero cuenta",
        "account",
        "account number",
        "conto",
        "kontonummer",
        "compte",
        "conta",
    ),
    "isin": ("isin", "codigo isin", "isin code"),
    "ticker": ("ticker", "simbolo", "symbol"),
    "symbol": (
        "simbolo",
        "symbol",
        "criptomoneda",
        "cryptocurrency",
        "crypto",
        "coin",
        "activo",
        "asset",
    ),
    "shares": (
        "participaciones",
        "no participaciones",
        "numero participaciones",
        "titulos",
        "no titulos",
        "acciones",
        "shares",
        "units",
        "quantity",
        "qty",
        "cantidad",
        "quote",
        "quantita",
        "stuck",
        "anzahl",
        "quantite",
        "quantidade",
    ),
    "currency_amount": (
        "cantidad",
        "quantity",
        "units",
        "qty",
        "quantita",
        "anzahl",
        "quantite",
        "quantidade",
    ),
    "price": (
        "precio",
        "precio unitario",
        "cotizacion",
        "valor liquidativo",
        "price",
        "unit price",
        "nav",
        "prezzo",
        "kurs",
        "prix",
        "preco",
    ),
    "fees": (
        "comision",
        "comisiones",
        "fees",
        "fee",
        "commission",
        "gastos",
        "commissioni",
        "gebuhr",
        "gebuhren",
        "frais",
        "taxas",
    ),
    "retentions": (
        "retencion",
        "retenciones",
        "withholding",
        "withholding tax",
        "impuestos",
        "ritenute",
        "ritenuta",
        "quellensteuer",
        "steuer",
        "impots",
        "impostos",
    ),
    "market": (
        "mercado",
        "bolsa",
        "market",
        "exchange",
        "mercato",
        "borsa",
        "borse",
        "marche",
    ),
    "split_ratio": ("ratio", "split ratio", "ratio split"),
    "portfolio_name": ("cartera", "portfolio", "portafoglio", "depot", "carteira"),
    "entity": ("entidad", "banco", "entity", "bank", "broker", "banca", "banque"),
    "interest_rate": ("tipo interes", "interes", "interest rate", "tae", "tasso"),
    "avg_balance": ("saldo medio", "average balance"),
    "total": ("saldo", "balance", "total", "saldo disponible", "kontostand", "solde"),
    "market_value": ("valor mercado", "valoracion", "market value", "valore mercato"),
    "initial_investment": (
        "inversion",
        "inversion inicial",
        "importe invertido",
        "initial investment",
        "invested",
        "cost",
    ),
    "average_buy_price": (
        "precio medio",
        "precio medio compra",
        "average price",
        "average buy price",
        "prezzo medio",
    ),
}

_NON_WORD = re.compile(r"[\W_]+")


def normalize_header(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value)).casefold()
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(_NON_WORD.sub(" ", text).split())


def header_tokens(value: Any) -> tuple[str, ...]:
    return tuple(
        token
        for token in normalize_header(value).split()
        if token not in HEADER_STOPWORDS
    )


_ALIAS_TOKENS: dict[str, list[tuple[str, ...]]] = {
    field: [header_tokens(alias) for alias in (*aliases, field)]
    for field, aliases in HEADER_ALIASES.items()
}


def header_alias_score(field: str, header: Any) -> Optional[tuple[int, int]]:
    tokens = header_tokens(header)
    if not tokens:
        return None

    aliases = _ALIAS_TOKENS.get(field) or [header_tokens(field)]
    best = None
    for rank, alias in enumerate(aliases):
        if not alias:
            continue
        if tokens == alias:
            score = (rank, 0)
        elif tokens[: len(alias)] == alias:
            score = (rank, 1)
        else:
            continue
        if best is None or score < best:
            best = score
    return best
