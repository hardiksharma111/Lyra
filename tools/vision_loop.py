import base64
import time
import random
import os
import subprocess
import re
import requests
from core.platform import IS_ANDROID

FLUTTER_URL = "http://127.0.0.1:5001/command"
GROQ_VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

APP_PACKAGE_MAP = {
    "settings": "com.android.settings",
    "chrome": "com.android.chrome",
    "youtube": "com.google.android.youtube",
    "whatsapp": "com.whatsapp",
    "instagram": "com.instagram.android",
    "play store": "com.android.vending",
    "spotify": "com.spotify.music",
    "brawl stars": "com.supercell.brawlstars",
    "telegram": "org.telegram.messenger",
    "gmail": "com.google.android.gm",
    "maps": "com.google.android.apps.maps",
}


def _extract_text_payload(task_description: str) -> str:
    """Extract quoted text first; otherwise parse after common action phrases."""
    q = re.search(r'"([^"]+)"|\'([^\']+)\'', task_description)
    if q:
        return (q.group(1) or q.group(2) or "").strip()

    lower = task_description.lower()
    for key in ("search ", "type ", "write "):
        idx = lower.find(key)
        if idx != -1:
            return task_description[idx + len(key):].strip()
    return ""


def _extract_replay_name(task_description: str) -> str:
    lower = task_description.lower().strip()
    for pat in (r"replay task\s+(.+)$", r"run task\s+(.+)$"):
        m = re.search(pat, lower)
        if m:
            return m.group(1).strip()
    return ""


def _run_template_task(task_description: str) -> str | None:
    """Run deterministic task templates without requiring screenshot vision."""
    from tools.adb_control import open_app, type_text, press_enter, replay_task

    lower_task = task_description.lower().strip()

    replay_name = _extract_replay_name(task_description)
    if replay_name:
        return replay_task(replay_name)

    pkg, app_name = _resolve_app_package(task_description)
    if any(k in lower_task for k in ["open ", "launch ", "play "]) and pkg:
        steps = [f"opened {app_name} ({pkg}) — {open_app(pkg)}"]

        if any(k in lower_task for k in ["search ", "type ", "write "]):
            payload = _extract_text_payload(task_description)
            if payload:
                steps.append(f"typed '{payload[:80]}' — {type_text(payload)}")
                steps.append(press_enter())

        return "Done: " + " | ".join(steps)

    return None


def _load_key(name: str) -> str:
    with open("Keys.txt") as f:
        for line in f:
            if line.startswith(name):
                return line.split("=", 1)[1].strip()
    raise ValueError(f"{name} not found")


def take_screenshot() -> str | None:
    """Capture screenshot and return base64 string.

    Priority on Android:
    1) Native screencap command (no Flutter capture dependency)
    2) Flutter capture endpoint fallback
    """
    if IS_ANDROID:
        tmp_path = "/data/data/com.termux/files/home/lyra_vision_screen.png"
        for bin_name in ("screencap", "/system/bin/screencap"):
            try:
                subprocess.run([bin_name, "-p", tmp_path], capture_output=True, text=True, timeout=8)
                if os.path.exists(tmp_path):
                    with open(tmp_path, "rb") as f:
                        data = f.read()
                    if data:
                        return base64.b64encode(data).decode()
            except Exception:
                continue

    # Fallback to Flutter screenshot endpoint.
    try:
        resp = requests.post(FLUTTER_URL, json={"action": "screenshot"}, timeout=10)
        data = resp.json()
        img_path = data.get("path")
        if img_path and os.path.exists(img_path):
            with open(img_path, "rb") as f:
                return base64.b64encode(f.read()).decode()
    except Exception:
        pass
    return None


def analyze_screen(screenshot_b64: str, task_description: str) -> dict:
    """
    Send screenshot to Groq vision model.
    Returns structured action JSON.
    """
    import re
    import json
    from groq import Groq
    client = Groq(api_key=_load_key("GROQ"))

    try:
        response = client.chat.completions.create(
            model=GROQ_VISION_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"}
                    },
                    {
                        "type": "text",
                        "text": f"""You are controlling an Android phone to complete this task: {task_description}

Look at the screenshot and decide the next action.
Respond with JSON only:
{{
    "action": "tap" | "swipe" | "wait" | "done" | "failed",
  "x": <screen x coordinate if tap>,
  "y": <screen y coordinate if tap>,
  "x1": <start x if swipe>,
  "y1": <start y if swipe>,
  "x2": <end x if swipe>,
  "y2": <end y if swipe>,
  "seconds": <seconds to wait if wait>,
  "reason": "why this action",
    "done": true if task is complete,
    "failed": true if task cannot proceed
}}"""
                    }
                ]
            }],
            max_tokens=200
        )
        text = response.choices[0].message.content
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception as e:
        return {
            "action": "failed",
            "done": True,
            "failed": True,
            "reason": f"Vision analysis error: {e}"
        }
    return {"action": "failed", "done": True, "failed": True, "reason": "Analysis failed"}


def _resolve_app_package(task_description: str) -> tuple[str | None, str | None]:
    lower = task_description.lower().strip()
    # Prefer longer names first (e.g., "play store" before "play").
    for app_name in sorted(APP_PACKAGE_MAP.keys(), key=len, reverse=True):
        if app_name in lower:
            return APP_PACKAGE_MAP[app_name], app_name
    return None, None


def run_vision_task(task_description: str, max_steps: int = 20) -> str:
    """
    Main vision loop. Takes screenshot, analyzes, acts, repeats.
    """
    from tools.adb_control import tap, swipe, open_app

    if not IS_ANDROID:
        return "Vision loop requires Android — Flutter MediaProjection not available on Windows"

    template_result = _run_template_task(task_description)
    if template_result:
        return template_result

    # Fast-path app launches for common "open/play app" tasks, independent of screenshot availability.
    lower_task = task_description.lower().strip()
    if any(k in lower_task for k in ["open ", "launch ", "play "]):
        pkg, app_name = _resolve_app_package(task_description)
        if pkg:
            open_result = open_app(pkg)
            return f"Done: opened {app_name} ({pkg}) — {open_result}"

    results = []
    for step in range(max_steps):
        screenshot = take_screenshot()
        if not screenshot:
            # If screenshot path is unavailable, still try a package fallback for app-launch tasks.
            pkg, app_name = _resolve_app_package(task_description)
            if pkg:
                open_result = open_app(pkg)
                results.append(f"Done: fallback opened {app_name} ({pkg}) — {open_result}")
                break
            return "Could not take screenshot — is Flutter running?"

        decision = analyze_screen(screenshot, task_description)
        action = decision.get("action", "done")
        reason = decision.get("reason", "")

        if decision.get("failed") or action == "failed":
            results.append(f"Failed: {reason}")
            break

        if decision.get("done") or action == "done":
            results.append(f"Done: {reason}")
            break

        if action == "tap":
            x, y = decision.get("x", 0), decision.get("y", 0)
            tap(x, y)
            results.append(f"Step {step+1}: tap({x},{y}) — {reason}")
        elif action == "swipe":
            swipe(
                decision.get("x1", 0), decision.get("y1", 0),
                decision.get("x2", 0), decision.get("y2", 0)
            )
            results.append(f"Step {step+1}: swipe — {reason}")
        elif action == "wait":
            secs = float(decision.get("seconds", 1))
            time.sleep(secs)
            results.append(f"Step {step+1}: wait {secs}s — {reason}")
        else:
            results.append(f"Step {step+1}: unknown action '{action}' — {reason}")
            break

        time.sleep(random.uniform(0.5, 1.5))

    return "\n".join(results) if results else "No steps executed"