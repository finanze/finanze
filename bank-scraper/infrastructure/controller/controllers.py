from flask import request, jsonify

from domain.bank import Bank, BankFeature
from domain.use_cases.scrape import Scrape
from domain.use_cases.update_sheets import UpdateSheets


def map_features(features: list[str]) -> list[BankFeature]:
    try:
        return [BankFeature[feature] for feature in features]
    except ValueError:
        return []


class Controllers:
    def __init__(self, scrape: Scrape, update_sheets: UpdateSheets):
        self.__scrape = scrape
        self.__update_sheets = update_sheets

    async def scrape(self):
        body = request.json
        bank_str = body.get("bank", None)
        if not bank_str:
            return jsonify({"message": "Bank not provided"}), 400
        try:
            bank = Bank[bank_str]
        except ValueError:
            return jsonify({"message": f"Invalid bank {bank_str}"}), 400

        bank_feats = body.get("features", [])
        features = map_features(bank_feats)

        code = body.get("code", None)
        process_id = body.get("processId", None)

        login_args = {
            "code": code,
            "processId": process_id
        }
        result = await self.__scrape.execute(bank, features, login=login_args)

        response = {"code": result.code.name}
        if result.details:
            response["details"] = result.details
        if result.data:
            response["data"] = result.data
        return jsonify(response), 200

    def update_sheets(self):
        self.__update_sheets.execute()
        return "", 204
