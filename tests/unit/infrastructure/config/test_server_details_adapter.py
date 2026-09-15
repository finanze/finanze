import pytest

from domain.platform import Distribution
from infrastructure.config import server_details_adapter
from infrastructure.config.server_details_adapter import (
    detect_distribution,
    detect_os_version,
)


class TestDetectOsVersion:
    def test_returns_mac_version_on_macos(self, monkeypatch):
        monkeypatch.setattr(server_details_adapter.platform, "system", lambda: "Darwin")
        monkeypatch.setattr(
            server_details_adapter.platform,
            "mac_ver",
            lambda: ("15.3.1", ("", "", ""), "arm64"),
        )

        assert detect_os_version() == "15.3.1"

    def test_joins_release_and_build_on_windows(self, monkeypatch):
        monkeypatch.setattr(
            server_details_adapter.platform, "system", lambda: "Windows"
        )
        monkeypatch.setattr(
            server_details_adapter.platform,
            "win32_ver",
            lambda: ("11", "10.0.22631", "SP0", "Multiprocessor Free"),
        )

        assert detect_os_version() == "11 10.0.22631"

    def test_returns_kernel_release_on_linux(self, monkeypatch):
        monkeypatch.setattr(server_details_adapter.platform, "system", lambda: "Linux")
        monkeypatch.setattr(
            server_details_adapter.platform, "release", lambda: "6.8.0-51-generic"
        )

        assert detect_os_version() == "6.8.0-51-generic"

    def test_returns_none_when_unknown(self, monkeypatch):
        monkeypatch.setattr(server_details_adapter.platform, "system", lambda: "Linux")
        monkeypatch.setattr(server_details_adapter.platform, "release", lambda: "")

        assert detect_os_version() is None


class TestDetectDistribution:
    @pytest.fixture(autouse=True)
    def _no_container_markers(self, monkeypatch):
        monkeypatch.delenv("FINANZE_DISTRIBUTION", raising=False)
        monkeypatch.setattr(
            server_details_adapter.Path, "exists", lambda self: False, raising=False
        )
        monkeypatch.setattr(
            server_details_adapter.Path,
            "read_text",
            lambda self, *args, **kwargs: (_ for _ in ()).throw(OSError()),
            raising=False,
        )

    def test_uses_declared_distribution(self, monkeypatch):
        monkeypatch.setenv("FINANZE_DISTRIBUTION", "docker")

        assert detect_distribution() == Distribution.DOCKER

    def test_ignores_unknown_declared_distribution(self, monkeypatch):
        monkeypatch.setenv("FINANZE_DISTRIBUTION", "something")

        assert detect_distribution() == Distribution.DESKTOP

    def test_detects_docker_env_file(self, monkeypatch):
        monkeypatch.setattr(
            server_details_adapter.Path,
            "exists",
            lambda self: str(self) == "/.dockerenv",
            raising=False,
        )

        assert detect_distribution() == Distribution.DOCKER

    def test_detects_container_cgroup(self, monkeypatch):
        monkeypatch.setattr(
            server_details_adapter.Path,
            "read_text",
            lambda self, *args, **kwargs: "0::/kubepods/besteffort/pod123",
            raising=False,
        )

        assert detect_distribution() == Distribution.DOCKER

    def test_defaults_to_desktop(self):
        assert detect_distribution() == Distribution.DESKTOP
