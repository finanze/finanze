import logging

from infrastructure.controller.handler import handle_request


class Router:
    def __init__(self):
        self._routes = []
        self._logger = logging.getLogger(__name__)

    @property
    def logger(self):
        return self._logger

    def add(self, method, pattern, handler):
        self._routes.append((method, pattern, handler))

    def match(self, method, path):
        for m, pattern, handler in self._routes:
            if m != method:
                continue
            pat_parts = pattern.split("/")
            path_parts = path.split("/")
            if len(pat_parts) != len(path_parts):
                continue
            params = {}
            match = True
            for i, part in enumerate(pat_parts):
                if part.startswith("<") and part.endswith(">"):
                    params[part[1:-1]] = path_parts[i]
                elif part != path_parts[i]:
                    match = False
                    break
            if match:
                return handler, params
        return None, None

    async def handle(self, method, path, body, headers):
        return await handle_request(self, method, path, body, headers)
