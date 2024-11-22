from domain.bank import Bank
from domain.bank_data import BankGlobalPosition

SUMMARY_SHEET = "Summary"


def update_summary(sheet, global_position: dict[str, BankGlobalPosition], sheet_id: str):
    batch_update = {
        "value_input_option": "RAW",
        "data": [
            *map_unicaja_summary_cells(global_position.get(Bank.UNICAJA.name, {})),
            *map_myinvestor_summary_cells(global_position.get(Bank.MY_INVESTOR.name, {})),
            *map_tr_summary_cells(global_position.get(Bank.TRADE_REPUBLIC.name, {})),
        ],
    }

    request = sheet.values().batchUpdate(spreadsheetId=sheet_id, body=batch_update)

    request.execute()


def map_unicaja_summary_cells(unicaja_summary: BankGlobalPosition):
    if not unicaja_summary:
        return []

    cards = unicaja_summary.cards
    mortgage = unicaja_summary.mortgage
    return [
        {"range": f"{SUMMARY_SHEET}!K1", "values": [[unicaja_summary.date.isoformat()]]},
        # Account
        {"range": f"{SUMMARY_SHEET}!B3", "values": [[unicaja_summary.account.total]]},
        {"range": f"{SUMMARY_SHEET}!C3", "values": [[unicaja_summary.account.retained]]},
        {"range": f"{SUMMARY_SHEET}!D3", "values": [[unicaja_summary.account.interest]]},
        # Cards - Credit
        {"range": f"{SUMMARY_SHEET}!B6", "values": [[cards.credit.limit]]},
        {"range": f"{SUMMARY_SHEET}!C6", "values": [[cards.credit.used]]},
        # Cards - Debit
        {"range": f"{SUMMARY_SHEET}!B7", "values": [[cards.debit.limit]]},
        {"range": f"{SUMMARY_SHEET}!C7", "values": [[cards.debit.used]]},
        # Mortgage
        {"range": f"{SUMMARY_SHEET}!B10", "values": [[mortgage.currentInstallment]]},
        {"range": f"{SUMMARY_SHEET}!C10", "values": [[mortgage.loanAmount]]},
        {"range": f"{SUMMARY_SHEET}!D10", "values": [[mortgage.principalPaid]]},
        {"range": f"{SUMMARY_SHEET}!E10", "values": [[mortgage.principalOutstanding]]},
        {"range": f"{SUMMARY_SHEET}!F10", "values": [[mortgage.interestRate]]},
        {"range": f"{SUMMARY_SHEET}!G10", "values": [[mortgage.nextPaymentDate.isoformat()[:10]]]},
    ]


def map_myinvestor_summary_cells(myi_summary: BankGlobalPosition):
    if not myi_summary:
        return []

    cards = myi_summary.cards
    sego = myi_summary.investments.sego
    stocks = myi_summary.investments.stocks
    funds = myi_summary.investments.funds
    deposits = myi_summary.deposits
    return [
        {"range": f"{SUMMARY_SHEET}!K14", "values": [[myi_summary.date.isoformat()]]},
        # Account
        {"range": f"{SUMMARY_SHEET}!B16", "values": [[myi_summary.account.total]]},
        {"range": f"{SUMMARY_SHEET}!C16", "values": [[myi_summary.account.retained]]},
        {"range": f"{SUMMARY_SHEET}!D16", "values": [[myi_summary.account.interest]]},
        # Cards - Credit
        {"range": f"{SUMMARY_SHEET}!B19", "values": [[cards.credit.limit]]},
        {"range": f"{SUMMARY_SHEET}!C19", "values": [[cards.credit.used]]},
        # Cards - Debit
        {"range": f"{SUMMARY_SHEET}!B20", "values": [[cards.debit.limit]]},
        {"range": f"{SUMMARY_SHEET}!C20", "values": [[cards.debit.used]]},
        # Deposits
        {"range": f"{SUMMARY_SHEET}!B23", "values": [[deposits.total]]},
        {"range": f"{SUMMARY_SHEET}!C23", "values": [[deposits.totalInterests]]},
        {"range": f"{SUMMARY_SHEET}!D23", "values": [[deposits.weightedInterestRate]]},
        # Investments - Sego
        {"range": f"{SUMMARY_SHEET}!B26", "values": [[sego.invested]]},
        {"range": f"{SUMMARY_SHEET}!C26", "values": [[sego.invested]]},
        {"range": f"{SUMMARY_SHEET}!F26", "values": [[sego.wallet]]},
        {"range": f"{SUMMARY_SHEET}!D26", "values": [[len(sego.details)]]},
        {"range": f"{SUMMARY_SHEET}!E26", "values": [[sego.weightedInterestRate]]},
        # Investments - Stocks
        {"range": f"{SUMMARY_SHEET}!B27", "values": [[stocks.initialInvestment]]},
        {"range": f"{SUMMARY_SHEET}!C27", "values": [[stocks.marketValue]]},
        {"range": f"{SUMMARY_SHEET}!D27", "values": [[len(stocks.details)]]},
        # Investments - Funds
        {"range": f"{SUMMARY_SHEET}!B28", "values": [[funds.initialInvestment]]},
        {"range": f"{SUMMARY_SHEET}!C28", "values": [[funds.marketValue]]},
        {"range": f"{SUMMARY_SHEET}!D28", "values": [[len(funds.details)]]},
    ]


def map_tr_summary_cells(tr_summary: BankGlobalPosition):
    if not tr_summary:
        return []

    stocks = tr_summary.investments.stocks
    return [
        {"range": f"{SUMMARY_SHEET}!K31", "values": [[tr_summary.date.isoformat()]]},
        # Account
        {"range": f"{SUMMARY_SHEET}!B33", "values": [[tr_summary.account.total]]},
        # Investments - Stocks
        {"range": f"{SUMMARY_SHEET}!B36", "values": [[stocks.initialInvestment]]},
        {"range": f"{SUMMARY_SHEET}!C36", "values": [[stocks.marketValue]]},
        {"range": f"{SUMMARY_SHEET}!D36", "values": [[len(stocks.details)]]},
    ]
