import os
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Protocol


class ClaudeErrorKind(str, Enum):
    AUTH = "AUTH"
    BILLING = "BILLING"
    RATE_LIMIT = "RATE_LIMIT"
    MODEL = "MODEL"
    CLI_OUTDATED = "CLI_OUTDATED"
    OVERLOADED = "OVERLOADED"
    INVALID_REQUEST = "INVALID_REQUEST"
    UNREACHABLE = "UNREACHABLE"
    TIMEOUT = "TIMEOUT"
    RUNTIME = "RUNTIME"


class ClaudeAgentError(Exception):
    def __init__(self, kind: ClaudeErrorKind, message: str):
        self.kind = kind
        super().__init__(message)


class ClaudeOutcome(str, Enum):
    COMPLETED = "COMPLETED"
    INCOMPLETE = "INCOMPLETE"
    REFUSED = "REFUSED"


@dataclass(frozen=True)
class ClaudeModelEntry:
    id: str
    name: str
    effort_levels: tuple[str, ...] = ()


@dataclass(frozen=True)
class ClaudeCompletion:
    outcome: ClaudeOutcome
    text: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None


class ClaudeRuntimeHandle(Protocol):
    async def stop(self) -> None: ...

    async def complete(
        self,
        model: str,
        instructions: Optional[str],
        prompt: str,
        schema: Optional[dict],
        effort: Optional[str],
        timeout: float,
    ) -> ClaudeCompletion: ...


AUTH_ERRORS = {"authentication_failed", "oauth_org_not_allowed", "account_on_hold"}
OVERLOAD_ERRORS = {"overloaded", "server_error"}
CLI_OUTDATED_MARKERS = (
    "claude_code_version_too_old",
    "cli_version_too_old",
    "does not support this model; version",
)
BILLING_MARKERS = ("credit balance", "spend limit", "billing")

# Variables that would bypass the user's own Claude Code sign-in or nest a session.
# HOME and CLAUDE_CONFIG_DIR stay, they locate that sign-in.
CLEARED_ENV = {
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_API_KEY_OLD",
    "ANTHROPIC_API_TOKEN",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_CUSTOM_HEADERS",
    "AWS_BEARER_TOKEN_BEDROCK",
    "CLAUDE_CODE_USE_BEDROCK",
    "CLAUDE_CODE_USE_VERTEX",
    "CLAUDE_CODE_USE_FOUNDRY",
    "CLAUDE_CODE_ENTRYPOINT",
    "CLAUDE_CODE_CHILD_SESSION",
    "CLAUDECODE",
    "MAX_THINKING_TOKENS",
    "MAX_STRUCTURED_OUTPUT_RETRIES",
    "NODE_OPTIONS",
    "DEBUG",
}
QUIET_ENV = {
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
    "DISABLE_AUTOUPDATER": "1",
}
ISOLATION_SETTINGS = '{"disableAllHooks":true,"enabledPlugins":{}}'
EMPTY_MCP_CONFIG = '{"mcpServers":{}}'
# Only the sign-in is reused: no personal settings, CLAUDE.md, hooks, plugins, MCP or tools.
ISOLATION_ARGUMENTS = (
    "--setting-sources",
    "project",
    "--settings",
    ISOLATION_SETTINGS,
    "--strict-mcp-config",
    "--mcp-config",
    EMPTY_MCP_CONFIG,
    "--tools",
    "",
)


def claude_environment() -> dict[str, str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in CLEARED_ENV and not key.startswith("DISABLE_PROMPT_CACHING")
    }
    env.update(QUIET_ENV)
    return env


def classify_claude_error(
    category: Optional[str], status: Optional[int], text: str = ""
) -> ClaudeErrorKind:
    lowered = text.casefold()
    if any(marker in lowered for marker in CLI_OUTDATED_MARKERS):
        return ClaudeErrorKind.CLI_OUTDATED
    if category in AUTH_ERRORS or status in (401, 403):
        return ClaudeErrorKind.AUTH
    if (
        category == "billing_error"
        or status == 402
        or any(marker in lowered for marker in BILLING_MARKERS)
    ):
        return ClaudeErrorKind.BILLING
    if category == "rate_limit" or status == 429:
        return ClaudeErrorKind.RATE_LIMIT
    if category == "model_not_found" or status == 404:
        return ClaudeErrorKind.MODEL
    if category in OVERLOAD_ERRORS or (status is not None and status >= 500):
        return ClaudeErrorKind.OVERLOADED
    if category == "invalid_request" or status == 400:
        return ClaudeErrorKind.INVALID_REQUEST
    return ClaudeErrorKind.RUNTIME
