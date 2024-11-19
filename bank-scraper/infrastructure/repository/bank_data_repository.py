from dataclasses import asdict, is_dataclass
from datetime import date, datetime

from pymongo import MongoClient

from application.ports.bank_data_port import BankDataPort
from domain.bank import Bank
from domain.bank_data import BankData, Account, Investments, Cards, Card, Mortgage, SegoInvestments, FundInvestments, \
    StockInvestments, SegoDetail, FundDetail, StockDetail, BankAdditionalData, AccountAdditionalData


def convert_dates(obj):
    if isinstance(obj, dict):
        return {key: convert_dates(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_dates(element) for element in obj]
    elif isinstance(obj, date) and not isinstance(obj, datetime):
        return datetime.combine(obj, datetime.min.time())
    elif is_dataclass(obj):
        return convert_dates(asdict(obj))
    return obj


def map_bank_data_to_domain(data: dict) -> BankData:
    account_data = data.get("account", {})
    account = None
    if account_data:
        account_additional_data = None
        if account_data["additionalData"]:
            account_additional_data = AccountAdditionalData(
                averageInterestRate=account_data["additionalData"]["averageInterestRate"],
                remunerationType=account_data["additionalData"]["remunerationType"]
            )
        account = Account(
            total=account_data["total"],
            retained=account_data["retained"],
            interest=account_data["interest"],
            additionalData=account_additional_data
        )

    cards_data = data.get("cards", {})
    cards = Cards(
        credit=Card(limit=cards_data["credit"]["limit"], used=cards_data["credit"]["used"]),
        debit=Card(limit=cards_data["debit"]["limit"], used=cards_data["debit"]["used"])
    ) if cards_data else None

    investments_data = data.get("investments", {})
    investments = None
    if investments_data:
        sego_data = investments_data.get("sego", {})
        sego = SegoInvestments(
            invested=sego_data["invested"],
            wallet=sego_data["wallet"],
            weightedInterestRate=sego_data["weightedInterestRate"],
            details=[
                SegoDetail(
                    name=detail["name"],
                    amount=detail["amount"],
                    interestRate=detail["interestRate"],
                    maturity=detail["maturity"],
                    type=detail["type"]
                )
                for detail in sego_data["details"]
            ]
        ) if sego_data else None

        funds_data = investments_data.get("funds", {})
        funds = FundInvestments(
            initialInvestment=funds_data["initialInvestment"],
            marketValue=funds_data["marketValue"],
            details=[
                FundDetail(
                    name=detail["name"],
                    isin=detail["isin"],
                    market=detail["market"],
                    shares=detail["shares"],
                    initialInvestment=detail["initialInvestment"],
                    averageBuyPrice=detail["averageBuyPrice"],
                    marketValue=detail["marketValue"],
                    currency=detail["currency"],
                    currencySymbol=detail["currencySymbol"],
                    lastUpdate=detail["lastUpdate"]
                )
                for detail in funds_data["details"]
            ]
        ) if funds_data else None

        stocks_data = investments_data.get("stocks", {})
        stocks = StockInvestments(
            initialInvestment=stocks_data["initialInvestment"],
            marketValue=stocks_data["marketValue"],
            details=[
                StockDetail(
                    name=detail["name"],
                    ticker=detail["ticker"],
                    isin=detail["isin"],
                    market=detail["market"],
                    shares=detail["shares"],
                    initialInvestment=detail["initialInvestment"],
                    averageBuyPrice=detail["averageBuyPrice"],
                    marketValue=detail["marketValue"],
                    currency=detail["currency"],
                    currencySymbol=detail["currencySymbol"],
                    type=detail["type"],
                    subtype=detail["subtype"]
                )
                for detail in stocks_data["details"]
            ]
        ) if stocks_data else None

        investments = Investments(
            sego=sego,
            stocks=stocks,
            funds=funds
        )

    mortgage_data = data["mortgage"]
    mortgage = Mortgage(
        currentInstallment=mortgage_data["currentInstallment"],
        loanAmount=mortgage_data["loanAmount"],
        principalPaid=mortgage_data["principalPaid"],
        principalOutstanding=mortgage_data["principalOutstanding"],
        interestRate=mortgage_data["interestRate"],
        nextPaymentDate=mortgage_data["nextPaymentDate"]
    ) if mortgage_data else None

    additional_data = None
    if data["additionalData"]:
        additional_data = BankAdditionalData(
            maintenance=data["additionalData"]["maintenance"]
        )

    return BankData(
        lastUpdate=data["lastUpdate"],
        account=account,
        cards=cards,
        mortgage=mortgage,
        investments=investments,
        additionalData=additional_data
    )


class BankDataRepository(BankDataPort):
    def __init__(self, uri: str, db_name: str):
        self.client = MongoClient(uri)
        self.db = self.client[db_name]
        self.collection = self.db["banks_data"]

    def upsert_bank_data(self, bank: Bank, data: BankData):
        self.collection.update_one(
            {"bank": bank.name},
            {"$set": convert_dates(data)},
            upsert=True
        )

    def get_all_data(self) -> dict[str, BankData]:
        pipeline = [
            {
                "$group": {
                    "_id": "$bank",
                    "data": {"$first": "$$ROOT"}
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "bank": "$_id",
                    "data": {
                        "$arrayToObject": {
                            "$filter": {
                                "input": {"$objectToArray": "$data"},
                                "cond": {"$ne": ["$$this.k", "_id"]}
                            }
                        }
                    }
                }
            }
        ]
        result = list(self.collection.aggregate(pipeline))

        mapped_result = {}
        for entry in result:
            bank_name = entry["bank"]
            raw_data = entry["data"]

            bank_data = map_bank_data_to_domain(raw_data)

            mapped_result[bank_name] = bank_data

        return mapped_result

    def close(self):
        self.client.close()
