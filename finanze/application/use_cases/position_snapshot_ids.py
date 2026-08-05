from uuid import uuid4

from domain.global_position import CryptoCurrencies, GlobalPosition, ProductType


def regenerate_snapshot_ids(position: GlobalPosition):
    products = position.products
    accounts_container = products.get(ProductType.ACCOUNT)
    portfolios_container = products.get(ProductType.FUND_PORTFOLIO)
    account_id_map: dict = {}
    portfolio_id_map: dict = {}
    if accounts_container and hasattr(accounts_container, "entries"):
        for acc in accounts_container.entries:
            if hasattr(acc, "id"):
                old = getattr(acc, "id", None)
                new_id = uuid4()
                acc.id = new_id
                if old:
                    account_id_map[old] = new_id
    if portfolios_container and hasattr(portfolios_container, "entries"):
        for pf in portfolios_container.entries:
            if hasattr(pf, "id"):
                old = getattr(pf, "id", None)
                new_id = uuid4()
                pf.id = new_id
                if old:
                    portfolio_id_map[old] = new_id
    cards_container = products.get(ProductType.CARD)
    if cards_container and hasattr(cards_container, "entries"):
        for card in cards_container.entries:
            ra = getattr(card, "related_account", None)
            if ra in account_id_map:
                card.related_account = account_id_map[ra]
    if portfolios_container and hasattr(portfolios_container, "entries"):
        for pf in portfolios_container.entries:
            acc_id = getattr(pf, "account_id", None)
            if acc_id in account_id_map:
                pf.account_id = account_id_map[acc_id]
    funds_container = products.get(ProductType.FUND)
    if funds_container and hasattr(funds_container, "entries"):
        for fund in funds_container.entries:
            portfolio = getattr(fund, "portfolio", None)
            if portfolio and getattr(portfolio, "id", None) in portfolio_id_map:
                portfolio.id = portfolio_id_map[portfolio.id]
            acc_id = getattr(fund, "account_id", None)
            if acc_id in account_id_map:
                fund.account_id = account_id_map[acc_id]
    for product_type, container in products.items():
        if product_type in (ProductType.ACCOUNT, ProductType.FUND_PORTFOLIO):
            continue
        if not (container and hasattr(container, "entries")):
            continue
        container_entries = container.entries
        if isinstance(container, CryptoCurrencies):
            container_entries = [
                asset
                for wallet in container_entries
                if hasattr(wallet, "assets")
                for asset in wallet.assets
            ]
        for entry in container_entries:
            if hasattr(entry, "id"):
                entry.id = uuid4()
