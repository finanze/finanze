from flask import request, jsonify

from domain.bank import Bank
from domain.use_cases.scrape import Scrape
from domain.use_cases.update_sheets import UpdateSheets


class Controllers:
    def __init__(self, scrape: Scrape, update_sheets: UpdateSheets):
        self.__scrape = scrape
        self.__update_sheets = update_sheets

    async def scrape(self):
        body = request.json
        body_str = body.get("bank", None)
        if not body_str:
            return jsonify({"message": "Bank not provided"}), 400
        try:
            bank = Bank[body_str]
        except ValueError:
            return jsonify({"message": f"Invalid bank {body_str}"}), 400

        code = body.get("code", None)
        process_id = body.get("processId", None)

        result = await self.__scrape.execute(bank, {"code": code, "processId": process_id})

        response = {"code": result.code.name}
        if result.details:
            response["details"] = result.details
        if result.data:
            response["data"] = result.data
        return jsonify(response), 200

    def update_sheets(self):
        self.__update_sheets.execute()
        return "", 204
