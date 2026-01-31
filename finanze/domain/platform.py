from enum import Enum


class OS(str, Enum):
    ANDROID = "ANDROID"
    IOS = "IOS"
    WINDOWS = "WINDOWS"
    MACOS = "MACOS"
    LINUX = "LINUX"
