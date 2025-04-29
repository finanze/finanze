from flask import Flask
from flask.json.provider import DefaultJSONProvider
from flask_cors import CORS

from domain.dezimal import Dezimal
from infrastructure.controller import exception_handler


class DezimalJSONProvider(DefaultJSONProvider):

    def default(self, obj):
        if isinstance(obj, Dezimal):
            return float(obj)
        return super().default(obj)


class FlaskApp(Flask):
    json_provider_class = DezimalJSONProvider


def flask(controllers):
    app = FlaskApp(__name__)

    CORS(app)

    @app.route('/api/v1/scrape')
    async def get_available_sources():
        return await controllers.get_available_sources()

    @app.route('/api/v1/scrape', methods=['POST'])
    async def scrape():
        return await controllers.scrape()

    @app.route('/api/v1/entity/login', methods=['POST'])
    async def add_entity_login():
        return await controllers.add_entity_login()

    @app.route('/api/v1/scrape/virtual', methods=['POST'])
    async def virtual_scrape():
        return await controllers.virtual_scrape()

    @app.route('/api/v1/update-sheets', methods=['POST'])
    def update_sheets():
        return controllers.update_sheets()

    exception_handler.register_exception_handlers(app)

    return app
