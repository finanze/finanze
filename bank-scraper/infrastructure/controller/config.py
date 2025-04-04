from flask import Flask
from flask.json.provider import DefaultJSONProvider

from domain.dezimal import Dezimal


class DezimalJSONProvider(DefaultJSONProvider):

    def default(self, obj):
        if isinstance(obj, Dezimal):
            return float(obj)
        return super().default(obj)


class FlaskApp(Flask):
    json_provider_class = DezimalJSONProvider
