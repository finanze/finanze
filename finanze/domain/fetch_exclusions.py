from uuid import UUID

from domain.global_position import (
    Accounts,
    Cards,
    FundInvestments,
    FundPortfolio,
    FundPortfolios,
    GlobalPosition,
    ProductType,
)
from domain.settings import AccountExclusion
from domain.transactions import FundPortfolioTx, StockTx, Transactions, normalize_iban


class FetchExclusions:
    def __init__(self, rules: list[AccountExclusion]):
        self._ibans = frozenset(rule.value for rule in rules)

    def matches(self, iban: str | None) -> bool:
        return normalize_iban(iban) in self._ibans

    def apply_to_position(self, position: GlobalPosition) -> None:
        if not self._ibans:
            return

        accounts = position.products.get(ProductType.ACCOUNT)
        excluded_accounts: set[UUID] = set()
        if isinstance(accounts, Accounts):
            excluded_accounts = {
                account.id
                for account in accounts.entries
                if account.id is not None and self.matches(account.iban)
            }
            accounts.entries = [
                account
                for account in accounts.entries
                if not self.matches(account.iban)
            ]

        cards = position.products.get(ProductType.CARD)
        if isinstance(cards, Cards):
            cards.entries = [
                card
                for card in cards.entries
                if card.related_account not in excluded_accounts
            ]

        def excluded_portfolio(portfolio: FundPortfolio) -> bool:
            return portfolio.account_id in excluded_accounts or (
                portfolio.account is not None
                and (
                    portfolio.account.id in excluded_accounts
                    or self.matches(portfolio.account.iban)
                )
            )

        excluded_portfolios: set[UUID] = set()
        portfolios = position.products.get(ProductType.FUND_PORTFOLIO)
        if isinstance(portfolios, FundPortfolios):
            excluded_portfolios = {
                portfolio.id
                for portfolio in portfolios.entries
                if portfolio.id is not None and excluded_portfolio(portfolio)
            }
            portfolios.entries = [
                portfolio
                for portfolio in portfolios.entries
                if not excluded_portfolio(portfolio)
            ]

        funds = position.products.get(ProductType.FUND)
        if isinstance(funds, FundInvestments):
            funds.entries = [
                fund
                for fund in funds.entries
                if fund.portfolio is None
                or (
                    fund.portfolio.id not in excluded_portfolios
                    and not excluded_portfolio(fund.portfolio)
                )
            ]

    def apply_to_transactions(self, transactions: Transactions) -> None:
        if not self._ibans:
            return

        excluded_account_txs = {
            (tx.entity.id, tx.ref)
            for tx in transactions.account or []
            if self.matches(tx.iban)
        }
        excluded_investment_txs = {
            (tx.entity.id, tx.linked_tx)
            for tx in transactions.account or []
            if (tx.entity.id, tx.ref) in excluded_account_txs and tx.linked_tx
        }
        excluded_investment_txs.update(
            (tx.entity.id, tx.ref)
            for tx in transactions.investment or []
            if (isinstance(tx, FundPortfolioTx) and self.matches(tx.iban))
            or (
                isinstance(tx, StockTx)
                and (tx.entity.id, tx.linked_tx) in excluded_account_txs
            )
        )

        if transactions.account is not None:
            transactions.account = [
                tx
                for tx in transactions.account
                if (tx.entity.id, tx.ref) not in excluded_account_txs
                and (tx.entity.id, tx.linked_tx) not in excluded_investment_txs
            ]
        if transactions.investment is not None:
            transactions.investment = [
                tx
                for tx in transactions.investment
                if (tx.entity.id, tx.ref) not in excluded_investment_txs
            ]
