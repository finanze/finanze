from io import BytesIO
from pathlib import Path


class RequestWrapper:
    def __init__(self, method, path, body, headers, args):
        self.method = method
        self.path = path
        self.headers = headers or {}
        self._args = args  # Dict[str, List[str]]
        self.json = {}
        self.files = {}
        self.form = {}
        self.view_args = {}  # Path params
        self.content_type = self.headers.get("Content-Type") if self.headers else None

        if isinstance(body, dict):
            clean_json = {}
            for k, v in body.items():
                if isinstance(v, dict) and v.get("_type") == "file":
                    content = v.get("content")
                    if hasattr(content, "tobytes"):
                        content = content.tobytes()
                    f = BytesIO(content)
                    f.filename = v.get("name")
                    f.content_type = v.get("type")
                    f.content_length = len(content)
                    f.stream = BytesIO(content)
                    f.save = lambda p: Path(p).write_bytes(content)
                    self.files[k] = f
                else:
                    clean_json[k] = v
            self.json = clean_json
            self.form = clean_json

        if not self.content_type:
            if self.files:
                self.content_type = "multipart/form-data"
            else:
                self.content_type = "application/json"

    @property
    def args(self):
        return self

    def get(self, key, default=None):
        vals = self._args.get(key)
        # Handle '1' or 1
        return vals[0] if vals else default

    def getlist(self, key):
        return self._args.get(key, [])

    def get_json(self, silent: bool = False):
        try:
            return self.json
        except Exception:
            if silent:
                return None
            raise
