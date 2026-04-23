import inspect
from typing import Any, Dict, Optional


class _RequestProxy:
    def __init__(self) -> None:
        self._current = None

    def _set(self, req: Any) -> None:
        self._current = req

    def __getattr__(self, name: str) -> Any:
        if self._current is None:
            raise RuntimeError("Request object not set")

        if name in {"files", "form"}:

            async def _get_value():
                return getattr(self._current, name)

            return _get_value()

        if name == "get_json":

            async def _get_json(*args: Any, **kwargs: Any) -> Any:
                return self._current.get_json(*args, **kwargs)

            return _get_json

        return getattr(self._current, name)


request = _RequestProxy()


def set_request(req: Any) -> None:
    request._set(req)


def jsonify(obj: Any) -> "Response":
    return Response(data=obj, mimetype="application/json")


class Response:
    def __init__(
        self,
        data: Any = None,
        status: int = 200,
        headers: Optional[Dict[str, str]] = None,
        mimetype: Optional[str] = None,
    ) -> None:
        self.data = data
        self.status_code = status
        self.headers: Dict[str, str] = headers or {}
        self.mimetype = mimetype


async def send_file(
    stream,
    mimetype: Optional[str] = None,
    as_attachment: bool = False,
    attachment_filename: Optional[str] = None,
):
    headers: Dict[str, str] = {}
    if as_attachment and attachment_filename:
        headers["Content-Disposition"] = f'attachment; filename="{attachment_filename}"'

    data = stream
    if hasattr(stream, "read"):
        maybe_data = stream.read()
        data = await maybe_data if inspect.isawaitable(maybe_data) else maybe_data

    return Response(
        data=data,
        mimetype=mimetype,
        headers=headers,
    )
