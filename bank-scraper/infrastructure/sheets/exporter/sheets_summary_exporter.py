from dateutil.tz import tzlocal

from domain.financial_entity import Entity
from domain.global_position import GlobalPosition

SUMMARY_SHEET = "Summary"


def update_summary(sheet, global_position: dict[str, GlobalPosition], sheet_id: str):
    batch_update = {
        "value_input_option": "RAW",
        "data": [
            *map_unicaja_summary_cells(global_position.get(Entity.UNICAJA.name, {})),
            *map_myinvestor_summary_cells(global_position.get(Entity.MY_INVESTOR.name, {})),
            *map_tr_summary_cells(global_position.get(Entity.TRADE_REPUBLIC.name, {})),
            *map_urbanitae_summary_cells(global_position.get(Entity.URBANITAE.name, {})),
            *map_wecity_summary_cells(global_position.get(Entity.WECITY.name, {})),
            *map_sego_summary_cells(global_position.get(Entity.SEGO.name, {})),
        ],
    }

    request = sheet.values().batchUpdate(spreadsheetId=sheet_id, body=batch_update)

    request.execute()


def map_unicaja_summary_cells(unicaja_summary: GlobalPosition):
    if not unicaja_summary:
        return []

    cards = unicaja_summary.cards
    mortgage = unicaja_summary.mortgage
    base_rows = [
        {"range": f"{SUMMARY_SHEET}!K1", "values": [[unicaja_summary.date.astimezone(tz=tzlocal()).isoformat()]]},
        # Account
        {"range": f"{SUMMARY_SHEET}!B3", "values": [[unicaja_summary.account.total]]},
        {"range": f"{SUMMARY_SHEET}!C3", "values": [[unicaja_summary.account.retained]]},
        {"range": f"{SUMMARY_SHEET}!D3", "values": [[unicaja_summary.account.interest]]},
        {"range": f"{SUMMARY_SHEET}!E3", "values": [[unicaja_summary.account.additionalData.pendingTransfers]]},
        # Cards - Credit
        {"range": f"{SUMMARY_SHEET}!B6", "values": [[cards.credit.limit]]},
        {"range": f"{SUMMARY_SHEET}!C6", "values": [[cards.credit.used]]},
        # Cards - Debit
        {"range": f"{SUMMARY_SHEET}!B7", "values": [[cards.debit.limit]]},
        {"range": f"{SUMMARY_SHEET}!C7", "values": [[cards.debit.used]]},
    ]

    mortgage_rows = [
        # Mortgage
        {"range": f"{SUMMARY_SHEET}!B10", "values": [[mortgage.currentInstallment]]},
        {"range": f"{SUMMARY_SHEET}!C10", "values": [[mortgage.loanAmount]]},
        {"range": f"{SUMMARY_SHEET}!D10", "values": [[mortgage.principalPaid]]},
        {"range": f"{SUMMARY_SHEET}!E10", "values": [[mortgage.principalOutstanding]]},
        {"range": f"{SUMMARY_SHEET}!F10", "values": [[mortgage.interestRate]]},
        {"range": f"{SUMMARY_SHEET}!G10", "values": [[mortgage.nextPaymentDate.isoformat()[:10]]]}
    ] if mortgage else []

    return base_rows + mortgage_rows


def map_myinvestor_summary_cells(myi_summary: GlobalPosition):
    if not myi_summary:
        return []

    cards = myi_summary.cards
    stocks = myi_summary.investments.stocks
    funds = myi_summary.investments.funds
    deposits = myi_summary.deposits
    return [
        {"range": f"{SUMMARY_SHEET}!K14", "values": [[myi_summary.date.astimezone(tz=tzlocal()).isoformat()]]},
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
        # Investments - Stocks
        {"range": f"{SUMMARY_SHEET}!B27", "values": [[stocks.initialInvestment]]},
        {"range": f"{SUMMARY_SHEET}!C27", "values": [[stocks.marketValue]]},
        {"range": f"{SUMMARY_SHEET}!D27", "values": [[len(stocks.details)]]},
        # Investments - Funds
        {"range": f"{SUMMARY_SHEET}!B28", "values": [[funds.initialInvestment]]},
        {"range": f"{SUMMARY_SHEET}!C28", "values": [[funds.marketValue]]},
        {"range": f"{SUMMARY_SHEET}!D28", "values": [[len(funds.details)]]},
    ]


def map_tr_summary_cells(tr_summary: GlobalPosition):
    if not tr_summary:
        return []

    stocks = tr_summary.investments.stocks
    return [
        {"range": f"{SUMMARY_SHEET}!K31", "values": [[tr_summary.date.astimezone(tz=tzlocal()).isoformat()]]},
        # Account
        {"range": f"{SUMMARY_SHEET}!B33", "values": [[tr_summary.account.total]]},
        # Investments - Stocks
        {"range": f"{SUMMARY_SHEET}!B36", "values": [[stocks.initialInvestment]]},
        {"range": f"{SUMMARY_SHEET}!C36", "values": [[stocks.marketValue]]},
        {"range": f"{SUMMARY_SHEET}!D36", "values": [[len(stocks.details)]]},
    ]


def map_urbanitae_summary_cells(urbanitae_summary: GlobalPosition):
    if not urbanitae_summary:
        return []

    real_state_cf = urbanitae_summary.investments.realStateCF
    return [
        {"range": f"{SUMMARY_SHEET}!K42", "values": [[urbanitae_summary.date.astimezone(tz=tzlocal()).isoformat()]]},
        # Investments - Real State CF
        {"range": f"{SUMMARY_SHEET}!B43", "values": [[real_state_cf.invested]]},
        {"range": f"{SUMMARY_SHEET}!C43", "values": [[len(real_state_cf.details)]]},
        {"range": f"{SUMMARY_SHEET}!D43", "values": [[real_state_cf.weightedInterestRate]]},
        {"range": f"{SUMMARY_SHEET}!E43", "values": [[real_state_cf.wallet]]},
    ]


def map_wecity_summary_cells(wecity_summary: GlobalPosition):
    if not wecity_summary:
        return []

    real_state_cf = wecity_summary.investments.realStateCF
    return [
        {"range": f"{SUMMARY_SHEET}!K49", "values": [[wecity_summary.date.astimezone(tz=tzlocal()).isoformat()]]},
        # Investments - Real State CF
        {"range": f"{SUMMARY_SHEET}!B50", "values": [[real_state_cf.invested]]},
        {"range": f"{SUMMARY_SHEET}!C50", "values": [[len(real_state_cf.details)]]},
        {"range": f"{SUMMARY_SHEET}!D50", "values": [[real_state_cf.weightedInterestRate]]},
        {"range": f"{SUMMARY_SHEET}!E50", "values": [[real_state_cf.wallet]]},
    ]


def map_sego_summary_cells(sego_summary: GlobalPosition):
    if not sego_summary:
        return []

    factoring = sego_summary.investments.factoring
    return [
        {"range": f"{SUMMARY_SHEET}!K56", "values": [[sego_summary.date.astimezone(tz=tzlocal()).isoformat()]]},
        # Investments - Wallet
        {"range": f"{SUMMARY_SHEET}!B58", "values": [[factoring.wallet]]},
        # Investments - Factoring
        {"range": f"{SUMMARY_SHEET}!B61", "values": [[factoring.invested]]},
        {"range": f"{SUMMARY_SHEET}!C61", "values": [[len(factoring.details)]]},
        {"range": f"{SUMMARY_SHEET}!D61", "values": [[factoring.weightedInterestRate]]},
    ]
