import datetime
from pathlib import Path

from domain.dezimal import Dezimal
from flask import Flask
from flask.json.provider import DefaultJSONProvider
from flask_cors import CORS
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


def flask(static_upload_dir: Path):
    app = FlaskApp(
        __name__,
        static_url_path="/static",
        static_folder=str(static_upload_dir.absolute()),
    )
    CORS(app)
    exception_handler.register_exception_handlers(app)
    app.config["MAX_CONTENT_LENGTH"] = 50 * 1000 * 1000
    return app
