import subprocess
import time
import random
import json
import os
from datetime import datetime
from core.platform import IS_ANDROID

# Saved task sequences for replay
TASKS_FILE = os.path.join("memory", "recorded_tasks.json")
JITTER_PIXELS = 3
MIN_ACTION_DELAY = 0.5
MAX_ACTION_DELAY = 1.5


def _run_android_cmd(args: list[str], timeout: int = 5) -> subprocess.CompletedProcess:
    """Run Android shell tools with a fallback to /system/bin path for Termux."""
    cmd = args[0]
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        return subprocess.run([f"/system/bin/{cmd}"] + args[1:], capture_output=True, text=True, timeout=timeout)


def _load_tasks() -> dict:
    if os.path.exists(TASKS_FILE):
        with open(TASKS_FILE) as f:
            return json.load(f)
    return {}


def _save_tasks(tasks: dict):
    os.makedirs(os.path.dirname(TASKS_FILE), exist_ok=True)
    with open(TASKS_FILE, "w") as f:
        json.dump(tasks, f, indent=2)


def _human_delay(min_seconds: float = MIN_ACTION_DELAY, max_seconds: float = MAX_ACTION_DELAY):
    time.sleep(random.uniform(min_seconds, max_seconds))


def tap(x: int, y: int, jitter: bool = True) -> str:
    """Tap at screen coordinate with optional human-like jitter."""
    if not IS_ANDROID:
        return f"ADB tap simulated at ({x}, {y}) — Android only in production"

    if jitter:
        x += random.randint(-JITTER_PIXELS, JITTER_PIXELS)
        y += random.randint(-JITTER_PIXELS, JITTER_PIXELS)

    try:
        _run_android_cmd(["input", "tap", str(x), str(y)], timeout=5)
        _human_delay()
        return f"Tapped ({x}, {y})"
    except Exception as e:
        return f"Tap failed: {e}"


def swipe(x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> str:
    """Swipe from one coordinate to another."""
    if not IS_ANDROID:
        return f"Swipe simulated — Android only"
    try:
        _run_android_cmd(["input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration_ms)], timeout=5)
        _human_delay()
        return f"Swiped ({x1},{y1}) → ({x2},{y2})"
    except Exception as e:
        return f"Swipe failed: {e}"


def type_text(text: str) -> str:
    """Type text via input command."""
    if not IS_ANDROID:
        return f"Type simulated: '{text}' — Android only"
    try:
        escaped = text.replace(' ', '%s').replace("'", "\\'")
        _run_android_cmd(["input", "text", escaped], timeout=5)
        _human_delay()
        return f"Typed: {text[:50]}"
    except Exception as e:
        return f"Type failed: {e}"


def press_back() -> str:
    """Press Android back button."""
    if not IS_ANDROID:
        return "Back press simulated"
    _run_android_cmd(["input", "keyevent", "4"], timeout=5)
    _human_delay()
    return "Back pressed"


def press_home() -> str:
    """Press Android home button."""
    if not IS_ANDROID:
        return "Home press simulated"
    _run_android_cmd(["input", "keyevent", "3"], timeout=5)
    _human_delay()
    return "Home pressed"


def open_app(package_name: str) -> str:
    """Open an app by package name."""
    if not IS_ANDROID:
        return f"App open simulated: {package_name}"
    try:
        # `am start` is more reliable from Termux than invoking `monkey` directly.
        _run_android_cmd([
            "am", "start", "-W",
            "-a", "android.intent.action.MAIN",
            "-c", "android.intent.category.LAUNCHER",
            package_name,
        ], timeout=10)
        _human_delay(1.0, 2.0)
        return f"Opened {package_name}"
    except Exception as e:
        return f"Open failed: {e}"


def record_task(name: str, steps: list) -> str:
    """
    Save a task sequence for later replay.
    steps = [{"action": "tap", "x": 100, "y": 200}, ...]
    """
    tasks = _load_tasks()
    tasks[name] = {
        "steps": steps,
        "recorded": datetime.now().isoformat()
    }
    _save_tasks(tasks)
    return f"Task '{name}' saved with {len(steps)} steps"


def replay_task(name: str) -> str:
    """Replay a recorded task sequence."""
    tasks = _load_tasks()
    if name not in tasks:
        available = list(tasks.keys())
        return f"Task '{name}' not found. Available: {available}"

    steps = tasks[name]["steps"]
    results = []

    for step in steps:
        action = step.get("action")
        if action == "tap":
            result = tap(step["x"], step["y"])
        elif action == "swipe":
            result = swipe(step["x1"], step["y1"], step["x2"], step["y2"])
        elif action == "type":
            result = type_text(step["text"])
        elif action == "back":
            result = press_back()
        elif action == "home":
            result = press_home()
        elif action == "wait":
            time.sleep(step.get("seconds", 1))
            result = f"Waited {step.get('seconds', 1)}s"
        else:
            result = f"Unknown action: {action}"
        results.append(result)

    return f"Task '{name}' completed: " + " | ".join(results)


def list_tasks() -> str:
    """List all recorded tasks."""
    tasks = _load_tasks()
    if not tasks:
        return "No recorded tasks yet."
    lines = [f"{name}: {len(t['steps'])} steps" for name, t in tasks.items()]
    return "\n".join(lines)