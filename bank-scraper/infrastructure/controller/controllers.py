from flask import request, jsonify

from domain.financial_entity import Entity, Feature
from domain.use_cases.get_available_sources import GetAvailableSources
from domain.use_cases.scrape import Scrape
from domain.use_cases.update_sheets import UpdateSheets
from domain.use_cases.virtual_scrape import VirtualScrape


def map_features(features: list[str]) -> list[Feature]:
    return [Feature[feature] for feature in features]


class Controllers:
    def __init__(self,
                 get_available_sources: GetAvailableSources,
                 scrape: Scrape,
                 update_sheets: UpdateSheets,
                 virtual_scrape: VirtualScrape):
        self._get_available_sources = get_available_sources
        self._scrape = scrape
        self._update_sheets = update_sheets
        self._virtual_scrape = virtual_scrape

    async def get_available_sources(self):
        available_sources = await self._get_available_sources.execute()
        return jsonify(available_sources), 200

    async def scrape(self):
        body = request.json
        entity_field = body.get("entity", None)
        if not entity_field:
            return jsonify({"message": "Source entity not provided"}), 400
        try:
            entity = Entity[entity_field]
        except ValueError:
            return jsonify({"message": f"Invalid entity {entity_field}"}), 400

        feature_fields = body.get("features", [])
        try:
            features = map_features(feature_fields)
        except KeyError as e:
            return jsonify({"message": f"Invalid feature {e}"}), 400

        code = body.get("code", None)
        process_id = body.get("processId", None)
        avoid_new_login = body.get("avoidNewLogin", False)

        login_args = {
            "code": code,
            "processId": process_id,
            "avoidNewLogin": avoid_new_login,
        }
        result = await self._scrape.execute(entity, features, login=login_args)

        response = {"code": result.code.name}
        if result.details:
            response["details"] = result.details
        if result.data:
            response["data"] = result.data
        return jsonify(response), 200

    def update_sheets(self):
        self._update_sheets.execute()
        return "", 204

    async def virtual_scrape(self):
        result = await self._virtual_scrape.execute()

        response = {"code": result.code.name}
        if result.data:
            response["data"] = result.data
        return jsonify(response), 200
