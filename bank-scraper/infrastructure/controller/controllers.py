from uuid import UUID

from flask import request, jsonify

from domain.financial_entity import Feature
from domain.login import TwoFactor, LoginOptions, LoginRequest
from domain.scrap_result import ScrapRequest
from domain.use_cases.add_entity_credentials import AddEntityCredentials
from domain.use_cases.get_available_entities import GetAvailableEntities
from domain.use_cases.scrape import Scrape
from domain.use_cases.update_sheets import UpdateSheets
from domain.use_cases.virtual_scrape import VirtualScrape


def map_features(features: list[str]) -> list[Feature]:
    return [Feature[feature] for feature in features]


class Controllers:
    def __init__(self,
                 get_available_entities: GetAvailableEntities,
                 scrape: Scrape,
                 update_sheets: UpdateSheets,
                 virtual_scrape: VirtualScrape,
                 add_entity_credentials: AddEntityCredentials):
        self._get_available_entities = get_available_entities
        self._scrape = scrape
        self._update_sheets = update_sheets
        self._virtual_scrape = virtual_scrape
        self._add_entity_credentials = add_entity_credentials

    async def get_available_sources(self):
        available_sources = await self._get_available_entities.execute()
        return jsonify(available_sources), 200

    async def add_entity_login(self):
        body = request.json
        entity = body.get("entity", None)
        if not entity:
            return jsonify({"message": "Source entity not provided"}), 400

        entity = UUID(entity)

        credentials = body.get("credentials", None)
        if not credentials:
            return jsonify({"message": "Credentials not provided"}), 400

        code = body.get("code", None)
        process_id = body.get("processId", None)

        login_request = LoginRequest(
            entity_id=entity,
            credentials=credentials,
            two_factor=TwoFactor(code=code, process_id=process_id)
        )
        result = await self._add_entity_credentials.execute(login_request)

        response = {"code": result.code}
        if result.message:
            response["message"] = result.message
        if result.details:
            response["details"] = result.details
        if result.process_id:
            response["processId"] = result.process_id
        return jsonify(response), 200

    async def scrape(self):
        body = request.json

        entity = body.get("entity", None)
        if not entity:
            return jsonify({"message": "Source entity not provided"}), 400

        entity = UUID(entity)

        feature_fields = body.get("features", [])
        try:
            features = map_features(feature_fields)
        except KeyError as e:
            return jsonify({"message": f"Invalid feature {e}"}), 400

        code = body.get("code", None)
        process_id = body.get("processId", None)
        avoid_new_login = body.get("avoidNewLogin", False)

        scrape_request = ScrapRequest(
            entity_id=entity,
            features=features,
            two_factor=TwoFactor(code=code, process_id=process_id),
            options=LoginOptions(avoid_new_login=avoid_new_login)
        )
        result = await self._scrape.execute(scrape_request)

        response = {"code": result.code}
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
