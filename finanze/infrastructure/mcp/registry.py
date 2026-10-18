import functools
import inspect
from typing import Any, Awaitable, Callable, Optional

from application.ports.error_reporter_port import ErrorReporterPort
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from infrastructure.mcp.errors import map_error
from infrastructure.mcp.serialization import to_json

ToolFn = Callable[..., Awaitable[Any]]


class ToolRegistry:
    def __init__(
        self,
        server: MCPServer,
        writes_enabled: bool,
        error_reporter: Optional[ErrorReporterPort] = None,
    ):
        self._server = server
        self.writes_enabled = writes_enabled
        self._error_reporter = error_reporter

    def read(self, title: str, open_world: bool = False):
        def decorator(fn: ToolFn) -> ToolFn:
            self._add(
                fn,
                ToolAnnotations(
                    title=title,
                    read_only_hint=True,
                    open_world_hint=open_world,
                ),
            )
            return fn

        return decorator

    def write(
        self,
        title: str,
        destructive: bool = False,
        idempotent: bool = False,
        open_world: bool = False,
    ):
        def decorator(fn: ToolFn) -> ToolFn:
            if self.writes_enabled:
                self._add(
                    fn,
                    ToolAnnotations(
                        title=title,
                        read_only_hint=False,
                        destructive_hint=destructive,
                        idempotent_hint=idempotent,
                        open_world_hint=open_world,
                    ),
                )
            return fn

        return decorator

    def _add(self, fn: ToolFn, annotations: ToolAnnotations):
        name = fn.__name__
        error_reporter = self._error_reporter

        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            try:
                result = await fn(*args, **kwargs)
            except ToolError:
                raise
            except Exception as e:
                raise map_error(name, e, error_reporter) from e
            return result if isinstance(result, str) else to_json(result)

        self._server.add_tool(
            wrapper,
            name=name,
            title=annotations.title,
            description=inspect.getdoc(fn),
            annotations=annotations,
            structured_output=False,
        )
