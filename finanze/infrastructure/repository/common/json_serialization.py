import json

from domain.dezimal import Dezimal


class DezimalJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Dezimal):
            return float(obj)
        return super().default(obj)
