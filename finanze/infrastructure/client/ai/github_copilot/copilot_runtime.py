import logging
import os
from typing import Any, Optional

from copilot import CopilotClient, RuntimeConnection
from copilot.rpc import (
    ModelPolicyState,
    ModelsListRequest,
    ModelsListTokenPriceUnitsRequest,
    PermissionDecisionReject,
    TokenPriceUnit,
)
from copilot.session_events import AssistantMessageData, SessionErrorData
from domain.ai import AIModelPricing, AIVisionLimits
from domain.dezimal import Dezimal

from infrastructure.agent_runtime.runtime_sandbox import AgentRuntimeInstanceDirs
from infrastructure.client.ai.github_copilot.copilot_runtime_types import (
    CopilotErrorKind,
    CopilotModelEntry,
    CopilotRuntimeError,
    classify_copilot_error,
)

TELEMETRY_DISABLED_ENV = "COPILOT_GITHUB_TELEMETRY_DISABLED"
CREDENTIAL_ENV_VARS = {
    "COPILOT_GITHUB_TOKEN",
    "GH_TOKEN",
    "GITHUB_TOKEN",
    "GH_ENTERPRISE_TOKEN",
    "GITHUB_ENTERPRISE_TOKEN",
    "GITHUB_COPILOT_API_TOKEN",
    "COPILOT_API_URL",
}
MODELS_TIMEOUT_SECONDS = 30
APPLICATION_NAME = "Finanze"
AI_CREDIT_USD = Dezimal("0.01")
AI_CREDITS_PER_PRICE_UNIT = {
    TokenPriceUnit.AI_CREDITS: Dezimal(1),
    TokenPriceUnit.NANO_AIU: Dezimal("0.000000001"),
}
MILLION_TOKENS = 1_000_000
PRICE_DECIMALS = 6

_log = logging.getLogger(__name__)


def _reject_permission(request: Any, invocation: Any) -> PermissionDecisionReject:
    return PermissionDecisionReject(feedback="Tools are disabled")


def _runtime_env() -> dict[str, str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in CREDENTIAL_ENV_VARS
    }
    env[TELEMETRY_DISABLED_ENV] = "true"
    return env


def _usd_per_million(
    price: float, batch_size: int, credits_per_unit: Dezimal
) -> Dezimal:
    credits = Dezimal(price) * credits_per_unit * MILLION_TOKENS / batch_size
    return round(credits * AI_CREDIT_USD, PRICE_DECIMALS)


def _pricing(billing: Any, unit: Optional[TokenPriceUnit]) -> Optional[AIModelPricing]:
    prices = getattr(billing, "token_prices", None)
    credits_per_unit = AI_CREDITS_PER_PRICE_UNIT.get(unit)
    if (
        prices is None
        or credits_per_unit is None
        or not prices.batch_size
        or prices.input_price is None
        or prices.output_price is None
    ):
        return None
    return AIModelPricing(
        input_per_million=_usd_per_million(
            prices.input_price, prices.batch_size, credits_per_unit
        ),
        output_per_million=_usd_per_million(
            prices.output_price, prices.batch_size, credits_per_unit
        ),
    )


def _vision_limits(capabilities: Any) -> Optional[AIVisionLimits]:
    vision = getattr(getattr(capabilities, "limits", None), "vision", None)
    if vision is None:
        return None
    media_types = getattr(vision, "supported_media_types", None)
    return AIVisionLimits(
        max_images=getattr(vision, "max_prompt_images", None),
        max_image_bytes=getattr(vision, "max_prompt_image_size", None),
        media_types=list(media_types) if media_types else None,
    )


def _to_entry(model: Any, unit: Optional[TokenPriceUnit]) -> CopilotModelEntry:
    policy = getattr(model, "policy", None)
    enabled = policy is None or policy.state == ModelPolicyState.ENABLED
    capabilities = getattr(model, "capabilities", None)
    supports = getattr(capabilities, "supports", None)
    efforts = ()
    if supports is not None and supports.reasoning_effort:
        efforts = tuple(model.supported_reasoning_efforts or ())
    vision = getattr(supports, "vision", None)
    return CopilotModelEntry(
        id=model.id,
        name=model.name or model.id,
        enabled=enabled,
        reasoning_efforts=efforts,
        pricing=_pricing(getattr(model, "billing", None), unit),
        vision=vision if isinstance(vision, bool) else None,
        vision_limits=_vision_limits(capabilities) if vision else None,
    )


async def _force_stop(client: CopilotClient):
    try:
        await client.force_stop()
    except Exception:
        _log.debug("Could not force stop the GitHub Copilot runtime", exc_info=True)


class CopilotRuntime:
    def __init__(self, client: CopilotClient, dirs: AgentRuntimeInstanceDirs):
        self._client = client
        self._dirs = dirs

    @classmethod
    async def start(
        cls, executable: str, token: str, dirs: AgentRuntimeInstanceDirs
    ) -> "CopilotRuntime":
        client = CopilotClient(
            connection=RuntimeConnection.for_stdio(path=executable),
            working_directory=str(dirs.work),
            log_level="error",
            env=_runtime_env(),
            github_token=token,
            base_directory=str(dirs.home),
            use_logged_in_user=False,
            client_info={"application_name": APPLICATION_NAME},
            mode="empty",
        )
        try:
            await client.start()
        except Exception as e:
            await _force_stop(client)
            raise CopilotRuntimeError(
                CopilotErrorKind.RUNTIME, "Could not start the GitHub Copilot runtime"
            ) from e
        return cls(client, dirs)

    async def stop(self):
        try:
            await self._client.stop()
        except Exception:
            await _force_stop(self._client)
        finally:
            await self._dirs.remove()

    async def is_authenticated(self) -> bool:
        try:
            status = await self._client.get_auth_status()
        except Exception as e:
            raise CopilotRuntimeError(
                classify_copilot_error(e),
                "Could not read the GitHub Copilot authentication status",
            ) from e
        return bool(status.isAuthenticated)

    async def list_models(self) -> list[CopilotModelEntry]:
        try:
            result = await self._client.rpc.models.list(
                ModelsListRequest(), timeout=MODELS_TIMEOUT_SECONDS
            )
        except Exception as e:
            raise CopilotRuntimeError(
                classify_copilot_error(e), "Could not list GitHub Copilot models"
            ) from e
        units = await self._price_units()
        return [_to_entry(model, units.get(model.id)) for model in result.models]

    async def _price_units(self) -> dict[str, TokenPriceUnit]:
        try:
            result = await self._client.rpc.models.list_token_price_units(
                ModelsListTokenPriceUnitsRequest(), timeout=MODELS_TIMEOUT_SECONDS
            )
        except Exception:
            _log.debug("Could not list GitHub Copilot price units", exc_info=True)
            return {}
        return {entry.model_id: entry.unit for entry in result.units}

    async def complete(
        self,
        model: str,
        instructions: Optional[str],
        prompt: str,
        schema: Optional[dict],
        reasoning_effort: Optional[str],
        timeout: float,
        attachments: Optional[list[dict]] = None,
    ) -> Optional[str]:
        session_errors: list[SessionErrorData] = []
        session = None
        try:
            session = await self._client.create_session(
                model=model,
                on_permission_request=_reject_permission,
                available_tools=[],
                system_message={"mode": "replace", "content": instructions or ""},
                infinite_sessions={"enabled": False},
                reasoning_effort=reasoning_effort,
                streaming=False,
                working_directory=str(self._dirs.work),
            )
            session.on(
                lambda event: (
                    session_errors.append(event.data)
                    if isinstance(event.data, SessionErrorData)
                    else None
                )
            )
            response = await session.send_and_wait(
                prompt,
                response_schema=schema,
                timeout=timeout,
                **({"attachments": attachments} if attachments else {}),
            )
        except Exception as e:
            raise CopilotRuntimeError(
                classify_copilot_error(
                    e, session_errors[-1] if session_errors else None
                ),
                "GitHub Copilot request failed",
            ) from e
        finally:
            if session is not None:
                await self._close_session(session)

        if response is None or not isinstance(response.data, AssistantMessageData):
            return None
        return response.data.content or None

    async def _close_session(self, session: Any):
        try:
            await session.disconnect()
        except Exception:
            _log.debug("Could not disconnect GitHub Copilot session", exc_info=True)
        try:
            await self._client.delete_session(session.session_id)
        except Exception:
            _log.debug("Could not delete GitHub Copilot session", exc_info=True)
