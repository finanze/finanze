from typing import Optional

from application.ports.error_reporter_port import ErrorReporterPort
from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette

from infrastructure.mcp.instructions import build_instructions
from infrastructure.mcp.registry import ToolRegistry
from infrastructure.mcp.tools import (
    calculations,
    cashflow,
    context,
    contributions,
    crypto,
    fetch,
    flows,
    historic,
    integrations,
    labeling,
    manual_positions,
    market,
    positions,
    real_estate,
    transactions,
)
from infrastructure.mcp.use_cases import McpUseCases

MCP_PATH = "/mcp"

_MODULES = [
    positions,
    manual_positions,
    contributions,
    historic,
    transactions,
    flows,
    labeling,
    cashflow,
    market,
    crypto,
    integrations,
    real_estate,
    calculations,
    fetch,
]


def build_mcp_server(
    ucs: McpUseCases,
    version: str,
    writes_enabled: bool,
    error_reporter: Optional[ErrorReporterPort] = None,
) -> MCPServer:
    server = MCPServer(
        name="finanze",
        title="Finanze",
        version=version,
        instructions=build_instructions(read_only=not writes_enabled),
    )
    registry = ToolRegistry(server, writes_enabled, error_reporter)
    context.register(registry, ucs, version)
    for module in _MODULES:
        module.register(registry, ucs)
    return server


def build_http_app(server: MCPServer) -> Starlette:
    return server.streamable_http_app(
        streamable_http_path=MCP_PATH,
        json_response=True,
        stateless_http=True,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=False
        ),
    )
