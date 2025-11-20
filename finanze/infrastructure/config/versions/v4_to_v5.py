TRANSACTION_ACCOUNT_VALUE = "ACCOUNT"
EXPORT_INVESTMENT_DATA = [
    "STOCK_ETF",
    "FUND",
    "FUND_PORTFOLIO",
    "FACTORING",
    "REAL_ESTATE_CF",
    "DEPOSIT",
]


def _transform_export_transactions_value(value):
    if value == "account":
        return TRANSACTION_ACCOUNT_VALUE
    if value == "investment":
        return list(EXPORT_INVESTMENT_DATA)
    return value


def _normalize_export_transactions_sheet(sheet: dict) -> None:
    data = sheet.get("data")
    if data is None:
        return

    if isinstance(data, list):
        normalized = []
        for item in data:
            transformed = _transform_export_transactions_value(item)
            if isinstance(transformed, list):
                normalized.extend(transformed)
            else:
                normalized.append(transformed)
        sheet["data"] = normalized
    elif isinstance(data, str):
        transformed = _transform_export_transactions_value(data)
        sheet["data"] = transformed


def _normalize_import_transactions_sheet(sheet: dict) -> None:
    data = sheet.get("data")
    if isinstance(data, list):
        if any(item == "investment" for item in data):
            sheet.pop("data", None)
        elif any(item == "account" for item in data):
            sheet["data"] = TRANSACTION_ACCOUNT_VALUE
        return

    if not isinstance(data, str):
        return

    if data == "account":
        sheet["data"] = TRANSACTION_ACCOUNT_VALUE
    elif data == "investment":
        sheet.pop("data", None)


def _iter_transaction_sheets(section: dict | None):
    if not isinstance(section, dict):
        return

    sheets = section.get("sheets")
    if not isinstance(sheets, dict):
        return

    transactions = sheets.get("transactions")
    if not isinstance(transactions, list):
        return

    for sheet in transactions:
        if isinstance(sheet, dict):
            yield sheet


def migrate(data: dict) -> dict:
    for sheet in _iter_transaction_sheets(data.get("export")):
        _normalize_export_transactions_sheet(sheet)

    for sheet in _iter_transaction_sheets(data.get("importing")):
        _normalize_import_transactions_sheet(sheet)

    data["version"] = 5
    return data
