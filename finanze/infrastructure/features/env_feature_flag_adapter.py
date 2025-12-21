import logging
import os
from typing import Optional

from application.ports.feature_flag_port import FeatureFlagPort
from domain.status import FeatureFlags, FFValue


class EnvFeatureFlagAdapter(FeatureFlagPort):
    _FF_PREFIX = "FF_"

    def __init__(self):
        self._log = logging.getLogger(__name__)
        self._features: FeatureFlags = self._load_features()

    def _load_features(self) -> FeatureFlags:
        features: FeatureFlags = {}
        for key, value in os.environ.items():
            if key.startswith(self._FF_PREFIX):
                feature_name = key[len(self._FF_PREFIX) :]
                features[feature_name] = value

        self._log.debug(f"Loaded {len(features)} feature flags: {features}")
        return features

    def get_all(self) -> FeatureFlags:
        return self._features.copy()

    def get_value(self, ff_name: str) -> Optional[FFValue]:
        return self._features.get(ff_name)
