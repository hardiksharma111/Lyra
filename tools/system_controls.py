import subprocess
import os
import psutil
import json
import winreg

APP_INDEX_FILE = "memory/app_index.json"

def build_app_index() -> dict:
    print("[Building app index from Windows installed apps...]")
    index = {}

    # Registry paths where Windows stores installed apps
    registry_paths = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]

    for hive, reg_path in registry_paths:
        try:
            key = winreg.OpenKey(hive, reg_path)
            for i in range(winreg.QueryInfoKey(key)[0]):
                try:
                    subkey_name = winreg.EnumKey(key, i)
                    subkey = winreg.OpenKey(key, subkey_name)

                    try:
                        name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                        install_location = None

                        # Try to get the actual executable
                        try:
                            install_location = winreg.QueryValueEx(subkey, "InstallLocation")[0]
                        except:
                            pass

                        try:
                            display_icon = winreg.QueryValueEx(subkey, "DisplayIcon")[0]
                            # DisplayIcon often points directly to the exe
                            if display_icon and ".exe" in display_icon.lower():
                                exe_path = display_icon.split(",")[0].strip().strip('"')
                                if os.path.exists(exe_path):
                                    index[name.lower()] = exe_path
                                    continue
                        except:
                            pass

                        # Search install location for main exe
                        if install_location and os.path.exists(install_location):
                            for f in os.listdir(install_location):
                                if f.endswith(".exe") and not any(x in f.lower() for x in ["uninstall", "setup", "update", "crash", "helper"]):
                                    full_path = os.path.join(install_location, f)
                                    index[name.lower()] = full_path
                                    break

                    except:
                        pass

                    winreg.CloseKey(subkey)
                except:
                    continue

            winreg.CloseKey(key)
        except:
            continue

    # Also add common apps that might be in PATH
    common_apps = {
        "notepad": "notepad.exe",
        "calculator": "calc.exe",
        "paint": "mspaint.exe",
        "task manager": "taskmgr.exe",
        "file explorer": "explorer.exe",
        "explorer": "explorer.exe",
        "command prompt": "cmd.exe",
        "powershell": "powershell.exe",
        "wordpad": "wordpad.exe",
    }
    index.update(common_apps)

    os.makedirs("memory", exist_ok=True)
    with open(APP_INDEX_FILE, "w") as f:
        json.dump(index, f, indent=2)

    print(f"[App index built — {len(index)} apps found]")
    return index

def _load_app_index() -> dict:
    if not os.path.exists(APP_INDEX_FILE):
        return build_app_index()
    with open(APP_INDEX_FILE, "r") as f:
        return json.load(f)

def _find_app(app_name: str) -> str | None:
    index = _load_app_index()
    app_lower = app_name.lower().strip()

    # Exact match on app name
    if app_lower in index:
        return index[app_lower]

    # Partial match — app name contains search term or vice versa
    best_match = None
    best_score = 0

    for name, path in index.items():
        # Search term fully contained in app name
        if app_lower in name:
            score = len(app_lower) / len(name)
            if score > best_score:
                best_score = score
                best_match = path

        # App name fully contained in search term
        elif name in app_lower:
            score = len(name) / len(app_lower)
            if score > best_score:
                best_score = score
                best_match = path

        # Word by word match
        else:
            words = [w for w in app_lower.split() if len(w) >= 4]
            if words and all(word in name for word in words):
                best_match = path
                best_score = 0.5

    # Only return if reasonably confident
    if best_score > 0.3:
        return best_match

    return None

def open_app(app_name: str) -> str:
    found_path = _find_app(app_name)

    if found_path:
        try:
            subprocess.Popen(f'"{found_path}"', shell=True)
            return f"Opening {app_name}"
        except Exception as e:
            return f"Found {app_name} but could not open: {e}"

    # Last resort — Windows start command
    try:
        subprocess.Popen(f"start {app_name}", shell=True)
        return f"Trying to open {app_name}"
    except:
        pass

    return f"Could not find {app_name} on your system"

def set_volume(level: int) -> str:
    level = max(0, min(100, level))
    nircmd_level = int(level * 655.35)
    try:
        subprocess.run(f"nircmd.exe setsysvolume {nircmd_level}", shell=True, capture_output=True)
        return f"Volume set to {level}%"
    except Exception as e:
        return f"Could not set volume: {e}"

def mute_volume() -> str:
    try:
        subprocess.run("nircmd.exe mutesysvolume 1", shell=True)
        return "Muted"
    except Exception as e:
        return f"Could not mute: {e}"

def unmute_volume() -> str:
    try:
        subprocess.run("nircmd.exe mutesysvolume 0", shell=True)
        return "Unmuted"
    except Exception as e:
        return f"Could not unmute: {e}"

def volume_up(steps: int = 5) -> str:
    try:
        nircmd_step = int(steps * 655.35)
        subprocess.run(f"nircmd.exe changesysvolume {nircmd_step}", shell=True, capture_output=True)
        return "Volume increased"
    except Exception as e:
        return f"Could not increase volume: {e}"

def volume_down(steps: int = 5) -> str:
    try:
        nircmd_step = int(steps * 655.35)
        subprocess.run(f"nircmd.exe changesysvolume -{nircmd_step}", shell=True, capture_output=True)
        return "Volume decreased"
    except Exception as e:
        return f"Could not decrease volume: {e}"

def get_brightness() -> int:
    try:
        import screen_brightness_control as sbc
        return sbc.get_brightness()[0]
    except:
        return -1

def set_brightness(level: int) -> str:
    level = max(0, min(100, level))
    try:
        import screen_brightness_control as sbc
        sbc.set_brightness(level)
        return f"Brightness set to {level}%"
    except Exception as e:
        return f"Could not set brightness: {e}"

def get_battery() -> str:
    try:
        battery = psutil.sensors_battery()
        if battery is None:
            return "No battery detected"
        plugged = "plugged in" if battery.power_plugged else "on battery"
        return f"Battery at {round(battery.percent)}% and {plugged}"
    except Exception as e:
        return f"Could not get battery: {e}"

def lock_screen() -> str:
    os.system("rundll32.exe user32.dll,LockWorkStation")
    return "Screen locked"

def shutdown(delay_seconds: int = 30) -> str:
    os.system(f"shutdown /s /t {delay_seconds}")
    return f"Shutting down in {delay_seconds} seconds"

def cancel_shutdown() -> str:
    os.system("shutdown /a")
    return "Shutdown cancelled"

def get_system_status() -> str:
    try:
        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory()
        battery = get_battery()
        brightness = get_brightness()

        status = f"CPU at {cpu}%. "
        status += f"RAM using {ram.percent}% of {round(ram.total / (1024**3))}GB. "
        status += f"{battery}. "
        if brightness != -1:
            status += f"Brightness at {brightness}%."

        return status
    except Exception as e:
        return f"Could not get system status: {e}"