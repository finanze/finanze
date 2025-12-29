import json
import logging
import os
from typing import Optional, Any
from urllib.error import URLError
from urllib.request import urlopen

from application.ports.feature_flag_port import FeatureFlagPort
from domain.status import FeatureFlags, FFValue, FFStatus
from domain.user import User


class FeatureFlagClient(FeatureFlagPort):
    def __init__(self, users: list[User]):
        self._log = logging.getLogger(__name__)
        self._users = users
        self._feature_flag_url = (
            os.getenv("FEATURE_FLAG_URL") or "https://features.api.finanze.me"
        )
        self._features: FeatureFlags = self._load_features()

    def _load_features(self) -> FeatureFlags:
        if not self._feature_flag_url:
            self._log.info("No feature flag URL configured, using empty feature flags")
            return {}

        try:
            self._log.info(f"Fetching feature flags from {self._feature_flag_url}")
            with urlopen(self._feature_flag_url, timeout=4) as response:
                data = json.loads(response.read().decode("utf-8"))
                return self._evaluate_features(data)
        except URLError as e:
            self._log.error(f"Failed to fetch feature flags: {e}")
            return {}
        except json.JSONDecodeError as e:
            self._log.error(f"Failed to parse feature flags JSON: {e}")
            return {}
        except Exception as e:
            self._log.error(f"Unexpected error loading feature flags: {e}")
            return {}

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

        self._log.warning(f"Unknown target type: {target_type}")
        return False

    def _evaluate_id_target(self, target: dict[str, Any]) -> bool:
        include_list = target.get("include", [])

        user_hashed_ids = {user.hashed_id() for user in self._users}

        for hashed_id in include_list:
            if hashed_id in user_hashed_ids:
                return True

        return False

    def get_all(self) -> FeatureFlags:
        return self._features.copy()

    def get_value(self, ff_name: str) -> Optional[FFValue]:
        return self._features.get(ff_name)
