import datetime

from flask import Flask
from flask.json.provider import DefaultJSONProvider
from flask_cors import CORS

from domain.dezimal import Dezimal
from infrastructure.controller import exception_handler


class FJSONProvider(DefaultJSONProvider):

    def default(self, obj):
        if isinstance(obj, Dezimal):
            return float(obj)
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        if isinstance(obj, datetime.date):
            return obj.isoformat()
        return super().default(obj)


class FlaskApp(Flask):
    json_provider_class = FJSONProvider


def flask():
    app = FlaskApp(__name__)
    CORS(app)
    exception_handler.register_exception_handlers(app)
    return app

