import json
import logging
import os
import platform
from typing import Optional, Any

from application.ports.feature_flag_port import FeatureFlagPort
from domain.platform import OS
from domain.status import FeatureFlags, FFValue, FFStatus
from domain.user import User
from infrastructure.client.http.http_session import get_http_session


def _detect_os() -> OS | None:
    system = platform.system().upper()

    if system == "DARWIN":
        return OS.MACOS
    elif system == "WINDOWS":
        return OS.WINDOWS
    elif system == "LINUX":
        return OS.LINUX

    return None


class FeatureFlagClient(FeatureFlagPort):
    def __init__(self, users: list[User] = None, operative_system: Optional[OS] = None):
        self._log = logging.getLogger(__name__)
        self._users = users
        self._os = operative_system if operative_system is not None else _detect_os()
        self._feature_flag_url = (
            os.getenv("FEATURE_FLAG_URL") or "https://features.api.finanze.me"
        )
        self._features = {}
        self._session = get_http_session()

    async def load(self):
        if not self._feature_flag_url:
            self._log.info("No feature flag URL configured, using empty feature flags")
            return {}
        self._log.info(f"Fetching feature flags from {self._feature_flag_url}")

        try:
            resp = await self._session.get(
                self._feature_flag_url,
                timeout=4,
            )
            data = await resp.json()

            self._features = self._evaluate_features(data)

        except json.JSONDecodeError as e:
            self._log.error(f"Failed to parse feature flags JSON: {e}")

        except Exception as e:
            self._log.error(
                "Failed to fetch feature flags (%s): %r",
                type(e).__name__,
                e,
                exc_info=True,
            )

    def _evaluate_features(self, data: dict[str, Any]) -> FeatureFlags:
        result: FeatureFlags = {}
        features_config = data.get("features", {})

        for feature_name, feature_config in features_config.items():
            for status_value, status_config in feature_config.items():
                if self._evaluate_targets(status_config):
                    try:
                        result[feature_name] = FFStatus(status_value)
                    except ValueError:
                        result[feature_name] = status_value
                    break

        return result

    def _evaluate_targets(self, status_config: dict[str, Any]) -> bool:
        targets = status_config.get("target", [])

        for target in targets:
            if self._evaluate_target(target):
                return True

        return False

    def _evaluate_target(self, target: dict[str, Any]) -> bool:
        target_type = target.get("type")

        if target_type == "ALL":
            return True

        if target_type == "ID":
            return self._evaluate_id_target(target)

        if target_type == "OS":
            return self._evaluate_os_target(target)

        self._log.warning(f"Unknown target type: {target_type}")
        return False

    def _evaluate_id_target(self, target: dict[str, Any]) -> bool:
        include_list = target.get("include", [])

        user_hashed_ids = {user.hashed_id() for user in (self._users or [])}

        for hashed_id in include_list:
            if hashed_id in user_hashed_ids:
                return True

        return False

    def _evaluate_os_target(self, target: dict[str, Any]) -> bool:
        include_list = target.get("include", [])
        if self._os is None:
            return False
        return self._os.value in include_list

    def get_all(self) -> FeatureFlags:
        return self._features.copy()

    def get_value(self, ff_name: str) -> Optional[FFValue]:
        return self._features.get(ff_name)
