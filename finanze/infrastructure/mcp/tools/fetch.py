from typing import Annotated, Optional
from uuid import UUID

from domain.entity import Feature
from domain.entity_login import LoginConfirmationType, LoginOptions, TwoFactor
from domain.fetch_result import FetchOptions, FetchRequest, FetchResultCode
from pydantic import Field

from infrastructure.mcp.registry import ToolRegistry
from infrastructure.mcp.use_cases import McpUseCases

_SAFE_DETAILS = {
    "message": "message",
    "processId": "process_id",
    "wait": "wait_seconds",
    "lastUpdate": "last_update",
    "completedFeatures": "completed_features",
    "failedFeatures": "failed_features",
}

_NEXT_STEPS = {
    FetchResultCode.COOLDOWN: "Data was updated recently, wait wait_seconds before retrying.",
    FetchResultCode.FEATURE_NOT_SUPPORTED: "The entity does not support some requested features, retry with fewer features.",
    FetchResultCode.MANUAL_LOGIN: "The entity requires a manual login, ask the user to do it in the Finanze app.",
    FetchResultCode.NOT_LOGGED: "The user must log in to this entity in the Finanze app.",
    FetchResultCode.NO_CREDENTIALS_AVAILABLE: "The user must log in to this entity in the Finanze app.",
    FetchResultCode.NOT_CONNECTED: "The user must log in to this entity in the Finanze app.",
    FetchResultCode.LOGIN_REQUIRED: "The session expired, the user must log in again in the Finanze app.",
    FetchResultCode.INVALID_CREDENTIALS: "Stored credentials are invalid, the user must update them in the Finanze app.",
    FetchResultCode.INVALID_CODE: "The code was wrong or expired, call again without code to request a new one.",
    FetchResultCode.CURRENTLY_UNAVAILABLE: "The entity is currently unavailable, retry later.",
    FetchResultCode.REMOTE_FAILED: "The entity failed, retry later.",
    FetchResultCode.LINK_EXPIRED: "The bank link expired, the user must renew it in the Finanze app.",
    FetchResultCode.UNEXPECTED_LOGIN_ERROR: "Unexpected login error, the user should retry from the Finanze app.",
}


def _next_step(
    code: FetchResultCode, confirmation_type, details: dict
) -> Optional[str]:
    if code == FetchResultCode.CODE_REQUESTED:
        if details.get("challengeType"):
            return "The entity requires solving a challenge, the user must update it from the Finanze app."
        if confirmation_type == LoginConfirmationType.IN_APP:
            return "Ask the user to approve the login in the entity's app, then call this tool again with the returned process_id and no code."
        return "Ask the user for the code they received, then call this tool again with that code and the returned process_id."
    return _NEXT_STEPS.get(code)


def register(registry: ToolRegistry, ucs: McpUseCases):
    @registry.write(
        "Fetch entity data", category="connections", idempotent=False, open_world=True
    )
    async def fetch_entity_data(
        account_id: Annotated[
            UUID,
            Field(
                description="Entity account ID of a connected native entity, from list_entities."
            ),
        ],
        features: Annotated[
            list[Feature],
            Field(
                min_length=1,
                description="Data to fetch, must be supported by the entity.",
            ),
        ] = [Feature.POSITION],
        code: Annotated[
            Optional[str],
            Field(description="Two-factor code provided by the user."),
        ] = None,
        process_id: Annotated[
            Optional[str],
            Field(description="process_id returned by the previous call."),
        ] = None,
    ):
        """Fetch fresh data from a connected bank, broker or platform using its stored login. May require two-factor authentication: when code is CODE_REQUESTED follow next_step and call again. Never ask the user for passwords, logins are managed in the Finanze app."""
        result = await ucs.fetch_financial_data.execute(
            FetchRequest(
                entity_account_id=account_id,
                features=list(dict.fromkeys(features)),
                two_factor=TwoFactor(code=code, process_id=process_id),
                fetch_options=FetchOptions(),
                login_options=LoginOptions(),
            )
        )
        details = result.details or {}
        response = {"code": result.code}
        response.update(
            {
                safe_key: details[key]
                for key, safe_key in _SAFE_DETAILS.items()
                if details.get(key) is not None
            }
        )
        next_step = _next_step(result.code, result.confirmation_type, details)
        if next_step:
            response["next_step"] = next_step
        return response
