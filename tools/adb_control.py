import subprocess
import time
import random
import json
import os
import re
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


def _get_focused_window_snapshot() -> str:
    """Return lowercased focus lines only, not full dumpsys output."""
    try:
        proc = _run_android_cmd(["dumpsys", "window"], timeout=6)
        out = ((proc.stdout or "") + "\n" + (proc.stderr or "")).lower()
        focus_lines = []
        for line in out.splitlines():
            if "mcurrentfocus" in line or "mfocusedapp" in line:
                focus_lines.append(line.strip())
        return "\n".join(focus_lines)
    except Exception:
        return ""


def _list_launcher_packages() -> list[str]:
    """Return launchable package names discovered from Android package manager."""
    packages: set[str] = set()

    try:
        proc = _run_android_cmd(
            [
                "cmd", "package", "query-activities", "--brief",
                "-a", "android.intent.action.MAIN",
                "-c", "android.intent.category.LAUNCHER",
            ],
            timeout=10,
        )
        out = ((proc.stdout or "") + "\n" + (proc.stderr or ""))
        for raw in out.splitlines():
            line = raw.strip()
            if not line or "/" not in line:
                continue
            pkg = line.split("/", 1)[0].strip()
            if pkg and "." in pkg:
                packages.add(pkg)
    except Exception:
        pass

    # Fallback: all installed packages.
    if not packages:
        try:
            proc = _run_android_cmd(["pm", "list", "packages"], timeout=10)
            out = ((proc.stdout or "") + "\n" + (proc.stderr or ""))
            for raw in out.splitlines():
                line = raw.strip()
                if line.startswith("package:"):
                    pkg = line.split(":", 1)[1].strip()
                    if pkg:
                        packages.add(pkg)
        except Exception:
            pass

    return sorted(packages)


def resolve_app_package(app_query: str) -> str | None:
    """Resolve a human app query to best matching installed package name."""
    if not IS_ANDROID:
        return None

    query = (app_query or "").strip().lower()
    if not query:
        return None

    # If user already provided package-like input.
    if "." in query and re.fullmatch(r"[a-z0-9_\.]+", query):
        return query

    stop = {"app", "open", "launch", "play", "and", "the", "to"}
    tokens = [
        t for t in re.split(r"[^a-z0-9]+", query)
        if t and t not in stop and len(t) > 1
    ]
    if not tokens:
        return None

    best_pkg = None
    best_score = -10_000

    for pkg in _list_launcher_packages():
        pkg_l = pkg.lower()
        segments = [s for s in pkg_l.split(".") if s]

        score = 0
        matched = 0

        if query in pkg_l:
            score += 40

        for tok in tokens:
            if tok in segments:
                score += 20
                matched += 1
            elif tok in pkg_l:
                score += 8
                matched += 1
            else:
                score -= 6

        if matched == 0:
            continue

        if score > best_score:
            best_score = score
            best_pkg = pkg

    if best_pkg and best_score >= 8:
        return best_pkg
    return None


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
        cleaned = text.strip()
        if not cleaned:
            return "Typed: <empty>"

        # Word-by-word typing avoids `%s` parsing edge cases on some OEM builds.
        parts = [p for p in cleaned.split(" ") if p != ""]
        if len(parts) <= 1:
            escaped = cleaned.replace("'", "\\'")
            _run_android_cmd(["input", "text", escaped], timeout=5)
        else:
            for idx, word in enumerate(parts):
                escaped = word.replace("'", "\\'")
                _run_android_cmd(["input", "text", escaped], timeout=5)
                if idx < len(parts) - 1:
                    _run_android_cmd(["input", "keyevent", "62"], timeout=5)  # SPACE
        _human_delay()
        return f"Typed: {cleaned[:50]}"
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


def press_enter() -> str:
    """Press Enter key (KEYCODE_ENTER)."""
    if not IS_ANDROID:
        return "Enter press simulated"
    _run_android_cmd(["input", "keyevent", "66"], timeout=5)
    _human_delay()
    return "Enter pressed"


def open_app(package_name: str) -> str:
    """Open an app by package name."""
    if not IS_ANDROID:
        return f"App open simulated: {package_name}"
    try:
        # `am start` is more reliable from Termux than invoking `monkey` directly.
        am_result = _run_android_cmd([
            "am", "start", "-W",
            "-a", "android.intent.action.MAIN",
            "-c", "android.intent.category.LAUNCHER",
            package_name,
        ], timeout=10)

        am_out = ((am_result.stdout or "") + "\n" + (am_result.stderr or "")).lower()
        am_ok = (
            am_result.returncode == 0
            and "error" not in am_out
            and "unable to resolve" not in am_out
        )

        package = package_name.lower().strip()

        if not am_ok:
            monkey_result = _run_android_cmd(
                ["monkey", "-p", package_name, "-c", "android.intent.category.LAUNCHER", "1"],
                timeout=10,
            )
            monkey_out = ((monkey_result.stdout or "") + "\n" + (monkey_result.stderr or "")).lower()
            monkey_ok = monkey_result.returncode == 0 and "error" not in monkey_out
            _human_delay(1.0, 2.0)
            if monkey_ok:
                for _ in range(5):
                    snap = _get_focused_window_snapshot()
                    if package in snap:
                        return f"Opened {package_name} (fallback monkey)"
                    time.sleep(0.4)
                return f"Open failed: {package_name} not focused (stayed in current app)"
            return f"Open failed: am and monkey failed for {package_name}"

        _human_delay(1.0, 2.0)
        for _ in range(5):
            snap = _get_focused_window_snapshot()
            if package in snap:
                return f"Opened {package_name}"
            time.sleep(0.4)
        return f"Open failed: {package_name} not focused (stayed in current app)"
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
        elif action == "enter":
            result = press_enter()
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