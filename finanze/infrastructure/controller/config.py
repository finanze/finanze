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


def flask():
    app = FlaskApp(__name__)
    CORS(app)
    exception_handler.register_exception_handlers(app)
    return app
