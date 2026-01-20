import datetime
from pathlib import Path

from domain.dezimal import Dezimal
from quart import Quart
from quart.json.provider import DefaultJSONProvider
from quart_cors import cors
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


class QuartApp(Quart):
    json_provider_class = FJSONProvider


def quart(static_upload_dir: Path):
    app = QuartApp(
        __name__,
        static_url_path="/static",
        static_folder=str(static_upload_dir.absolute()),
    )
    cors(app, expose_headers=["Content-Disposition"])
    exception_handler.register_exception_handlers(app)
    app.config["MAX_CONTENT_LENGTH"] = 50 * 1000 * 1000
    return app
