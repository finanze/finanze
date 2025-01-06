from dataclasses import asdict, is_dataclass
from datetime import date, datetime, timezone
from enum import Enum
from typing import Optional

from pymongo import MongoClient

from application.ports.position_port import PositionPort
from domain.financial_entity import Entity
from domain.global_position import GlobalPosition, Account, Investments, Cards, Card, Mortgage, FactoringInvestments, \
    FundInvestments, \
    StockInvestments, FactoringDetail, FundDetail, StockDetail, PositionAdditionalData, AccountAdditionalData, Deposit, \
    Deposits, \
    RealStateCFInvestments, RealStateCFDetail


def map_serializable(obj):
    if isinstance(obj, dict):
        return {key: map_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [map_serializable(element) for element in obj]
    elif isinstance(obj, date) and not isinstance(obj, datetime):
        return datetime.combine(obj, datetime.min.time())
    elif is_dataclass(obj):
        return map_serializable(asdict(obj))
    elif isinstance(obj, Enum):
        return obj.name
    return obj


def map_data_to_domain(data: dict) -> GlobalPosition:
    account_data = data.get("account", {})
    account = None
    if account_data:
        account_additional_data = None
        if account_data["additionalData"]:
            account_additional_data = AccountAdditionalData(
                averageInterestRate=account_data["additionalData"].get("averageInterestRate", None),
                remunerationType=account_data["additionalData"].get("remunerationType", None),
                pendingTransfers=account_data["additionalData"].get("pendingTransfers", None)
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
        factoring_data = investments_data.get("factoring", {})
        factoring = FactoringInvestments(
            invested=factoring_data["invested"],
            weightedInterestRate=factoring_data["weightedInterestRate"],
            details=[
                FactoringDetail(
                    name=detail["name"],
                    amount=detail["amount"],
                    currency=detail.get("currency", None),
                    currencySymbol=detail.get("currencySymbol", None),
                    interestRate=detail["interestRate"],
                    netInterestRate=detail["netInterestRate"],
                    lastInvestDate=detail["lastInvestDate"],
                    maturity=detail["maturity"],
                    type=detail["type"],
                    state=detail["state"],
                )
                for detail in factoring_data["details"]
            ]
        ) if factoring_data else None

        rs_cf_data = investments_data.get("realStateCF", {})
        rs_cf = RealStateCFInvestments(
            invested=rs_cf_data["invested"],
            weightedInterestRate=rs_cf_data["weightedInterestRate"],
            details=[
                RealStateCFDetail(
                    name=detail["name"],
                    amount=detail["amount"],
                    currency=detail.get("currency", None),
                    currencySymbol=detail.get("currencySymbol", None),
                    interestRate=detail["interestRate"],
                    lastInvestDate=detail["lastInvestDate"],
                    months=detail["months"],
                    type=detail["type"],
                    businessType=detail["businessType"],
                    state=detail.get("state", None),
                    potentialExtension=detail.get("potentialExtension", None),
                )
                for detail in rs_cf_data["details"]
            ]
        ) if rs_cf_data else None

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

        deposits_data = investments_data.get("deposits", {})
        deposits = None
        if deposits_data:
            deposits = Deposits(
                total=deposits_data["total"],
                totalInterests=deposits_data["totalInterests"],
                weightedInterestRate=deposits_data["weightedInterestRate"],
                details=[
                    Deposit(
                        name=detail["name"],
                        amount=detail["amount"],
                        totalInterests=detail["totalInterests"],
                        interestRate=detail["interestRate"],
                        maturity=detail["maturity"],
                        creation=detail["creation"]
                    )
                    for detail in deposits_data["details"]
                ]
            )

        investments = Investments(
            factoring=factoring,
            stocks=stocks,
            funds=funds,
            realStateCF=rs_cf,
            deposits=deposits
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
        additional_data = PositionAdditionalData(
            maintenance=data["additionalData"]["maintenance"]
        )

    return GlobalPosition(
        date=data["date"].replace(tzinfo=timezone.utc),
        account=account,
        cards=cards,
        mortgage=mortgage,
        investments=investments,
        additionalData=additional_data
    )


class PositionRepository(PositionPort):
    def __init__(self, client: MongoClient, db_name: str):
        self.client = client
        self.db = self.client[db_name]
        self.collection = self.db["positions"]

    def save(self, entity: str, position: GlobalPosition):
        self.collection.insert_one(
            {"entity": entity, **map_serializable(position)}
        )

    def get_last_grouped_by_entity(self) -> dict[str, GlobalPosition]:
        pipeline = [
            {
                "$sort": {
                    "entity": 1,
                    "date": -1
                }
            },
            {
                "$group": {
                    "_id": "$entity",
                    "data": {"$first": "$$ROOT"}
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "entity": "$_id",
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
            entity_name = entry["entity"]
            raw_data = entry["data"]

            entity_data = map_data_to_domain(raw_data)

            mapped_result[entity_name] = entity_data

        return mapped_result

    def get_last_updated(self, entity: Entity) -> Optional[datetime]:
        result = self.collection.find_one(
            {"entity": entity.name},
            sort=[("date", -1)],
            projection={"_id": 0, "date": 1}
        )
        if not result:
            return None
        return result["date"].replace(tzinfo=timezone.utc)
