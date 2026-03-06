import os
import platform

def get_platform():
    if os.path.exists("/data/data/com.termux"):
        return "android"
    system = platform.system().lower()
    if system == "windows":
        return "windows"
    elif system == "linux":
        return "linux"
    elif system == "darwin":
        return "macos"
    return "unknown"

PLATFORM = get_platform()
IS_ANDROID = PLATFORM == "android"
IS_WINDOWS = PLATFORM == "windows"