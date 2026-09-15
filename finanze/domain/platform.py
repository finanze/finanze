from enum import Enum
from typing import Optional


class OS(str, Enum):
    ANDROID = "ANDROID"
    IOS = "IOS"
    WINDOWS = "WINDOWS"
    MACOS = "MACOS"
    LINUX = "LINUX"


class Distribution(str, Enum):
    DESKTOP = "desktop"
    DOCKER = "docker"
    MOBILE = "mobile"
    WEB = "web"


# Names as expected in the OS context of an error report
OS_NAMES = {
    OS.ANDROID: "Android",
    OS.IOS: "iOS",
    OS.WINDOWS: "Windows",
    OS.MACOS: "macOS",
    OS.LINUX: "Linux",
}

# The frontend uses its own platform names, and "web" maps to no OS at all
_OS_ALIASES = {os.value.lower(): os for os in OS} | {"mac": OS.MACOS}


def parse_os(value: Optional[str]) -> Optional[OS]:
    if not value:
        return None
    return _OS_ALIASES.get(value.strip().lower())
