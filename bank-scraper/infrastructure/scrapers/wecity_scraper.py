from datetime import datetime, date
from hashlib import sha1
from typing import Optional

from application.ports.entity_scraper import EntityScraper
from domain.financial_entity import Entity
from domain.global_position import GlobalPosition, RealStateCFDetail, RealStateCFInvestments, Investments, SourceType
from domain.transactions import Transactions, RealStateCFTx, TxType, TxProductType
from infrastructure.scrapers.wecity_client import WecityAPIClient

DATE_FORMAT = "%d/%m/%Y"


class WecityScraper(EntityScraper):

    def __init__(self):
        self.__client = WecityAPIClient()

    def login(self, credentials: tuple, **kwargs) -> Optional[dict]:
        username, password = credentials
        process_id = kwargs.get("processId", None)
        code = kwargs.get("code", None)
        avoid_new_login = kwargs.get("avoidNewLogin", False)
        return self.__client.login(username, password, avoid_new_login, process_id, code)

    async def global_position(self) -> GlobalPosition:
        wallet, investments_overview = self.__client.get_wallet_and_investments_overview()

        investment_details = []
        for inv in investments_overview:
            name = inv["name"]
            amount = inv["amount"]
            investments_details = self.__client.get_investment_details(inv["id"])

            raw_business_type = investments_details["businessType"]
            business_type = raw_business_type
            if raw_business_type == "Préstamo":
                business_type = "LENDING"

            raw_project_type = investments_details["type"]
            project_type = raw_project_type
            if raw_project_type == "Residencial":
                project_type = "HOUSING"
            elif raw_project_type == "Suelo":
                project_type = "FLOOR"

            txs = self.scrape_transactions()
            last_invest_date = max(
                [tx["date"] for tx in txs if "Inversión comprometida" in tx["category"] and tx["name"] == name],
                default=None)

            investment_details.append(
                RealStateCFDetail(
                    name=name,
                    amount=round(amount, 2),
                    interestRate=round(investments_details["interestRate"] / 100, 4),
                    lastInvestDate=last_invest_date,
                    months=investments_details["months"],
                    potentialExtension=investments_details["potentialExtension"],
                    type=project_type,
                    businessType=business_type,
                    state=None,
                )
            )

        total_invested = round(sum([inv.amount for inv in investment_details]), 2)
        weighted_interest_rate = round(
            (sum([inv.amount * inv.interestRate for inv in investment_details])
             / sum([inv.amount for inv in investment_details])),
            4,
        )
        investments = Investments(
            realStateCF=RealStateCFInvestments(
                invested=total_invested,
                wallet=wallet,
                weightedInterestRate=weighted_interest_rate,
                details=investment_details
            )
        )

        return GlobalPosition(
            investments=investments
        )

    async def transactions(self, registered_txs: set[str]) -> Transactions:
        raw_transactions = self.scrape_transactions()

        txs = []
        inv_by_am_date_name_type_count = {}
        for tx in raw_transactions:
            tx_type_raw = tx["category"]
            if "Ingreso de capital" in tx_type_raw:
                continue
            tx_type = TxType.INVESTMENT if "Inversión comprometida" in tx_type_raw else None
            if not tx_type:
                print(f"Skipping tx {tx['name']} with type {tx_type_raw}")
                continue

            name = tx["name"]
            amount = round(tx["amount"], 2)
            tx_date = tx["date"]
            amount_date_name_type = f"{amount}_{tx_date.isoformat()}_{name}_{tx_type}"

            count = inv_by_am_date_name_type_count.get(amount_date_name_type, 0) + 1
            ref = self.calc_tx_id(name, tx_date, amount, tx_type, count)
            inv_by_am_date_name_type_count[amount_date_name_type] = count

            if ref in registered_txs:
                continue

            txs.append(RealStateCFTx(
                id=ref,
                name=name,
                amount=amount,
                currency="EUR",
                currencySymbol="€",
                type=tx_type,
                date=tx_date,
                entity=Entity.WECITY,
                productType=TxProductType.REAL_STATE_CF,
                fees=0,
                retentions=0,
                interests=0,
                sourceType=SourceType.REAL
            ))

        return Transactions(investment=txs)

    def scrape_transactions(self):
        _, raw_txs = self.__client.get_wallet_and_transactions()

        txs = []
        for tx in raw_txs:
            txs.append(
                {
                    "date": datetime.strptime(tx["date"], DATE_FORMAT).date(),
                    "category": tx["category"],
                    "name": tx["name"],
                    "amount": round(tx["amount"], 2)
                }
            )

        return sorted(txs, key=lambda txx: (txx["date"], txx["amount"]))

    @staticmethod
    def calc_tx_id(inv_name: str,
                   tx_date: date,
                   amount: float,
                   tx_type: TxType,
                   repeat_counter: int) -> str:
        return sha1(
            f"W_{inv_name}_{tx_date.isoformat()}_{amount}_{tx_type}_{repeat_counter}".encode("UTF-8")).hexdigest()
