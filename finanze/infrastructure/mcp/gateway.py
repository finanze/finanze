import json

from domain.mcp import McpAccess
from domain.use_cases.authorize_mcp_access import AuthorizeMcpAccess

_DENIED = {
    McpAccess.DISABLED: (404, "MCP server is disabled"),
    McpAccess.LOCKED: (503, "Finanze is locked, log in to the app first"),
    McpAccess.UNAUTHORIZED: (401, "Invalid or missing token"),
}


class McpGateway:
    def __init__(
        self,
        default_app,
        read_app,
        full_app,
        authorize_mcp_access: AuthorizeMcpAccess,
        path: str = "/mcp",
    ):
        self._default_app = default_app
        self._read_app = read_app
        self._full_app = full_app
        self._authorize_mcp_access = authorize_mcp_access
        self._path = path

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not self._is_mcp_path(scope["path"]):
            await self._default_app(scope, receive, send)
            return

        access = await self._authorize_mcp_access.execute(_bearer_token(scope))
        if access == McpAccess.READ_WRITE:
            await self._full_app(scope, receive, send)
        elif access == McpAccess.READ_ONLY:
            await self._read_app(scope, receive, send)
        else:
            status, message = _DENIED[access]
            await _send_error(send, status, message)

    def _is_mcp_path(self, path: str) -> bool:
        return path == self._path or path.startswith(f"{self._path}/")


def _bearer_token(scope) -> str | None:
    for key, value in scope.get("headers", []):
        if key == b"authorization":
            scheme, _, token = value.decode("latin-1").partition(" ")
            if scheme.lower() == "bearer" and token.strip():
                return token.strip()
            return None
    return None


async def _send_error(send, status: int, message: str):
    body = json.dumps({"message": message}).encode("utf-8")
    headers = [
        (b"content-type", b"application/json"),
        (b"content-length", str(len(body)).encode("latin-1")),
    ]
    if status == 401:
        headers.append((b"www-authenticate", b"Bearer"))
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body})
