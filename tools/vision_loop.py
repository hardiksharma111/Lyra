import base64
import time
import random
import os
import subprocess
import re
import json
from datetime import datetime
import requests
from core.platform import IS_ANDROID

FLUTTER_URL = "http://127.0.0.1:5001/command"
GROQ_VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
PROVIDER_STATE_FILE = os.path.join("memory", "phase8_provider_state.json")
TRACE_LOG_FILE = os.path.join("memory", "phase8_trace.jsonl")

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

APP_ALIASES = {
    "yt": "youtube",
    "ytube": "youtube",
    "chrom": "chrome",
    "chorme": "chrome",
    "insta": "instagram",
    "ig": "instagram",
    "gm": "gmail",
    "gmap": "maps",
    "g maps": "maps",
    "bs": "brawl stars",
    "brawl": "brawl stars",
    "playstore": "play store",
}


def _trace(event: str, **data):
    """Append lightweight Phase 8 traces for debugging fallback and action quality."""
    try:
        os.makedirs(os.path.dirname(TRACE_LOG_FILE), exist_ok=True)
        row = {
            "ts": datetime.now().isoformat(),
            "event": event,
            **data,
        }
        with open(TRACE_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=True) + "\n")
    except Exception:
        # Tracing must never break task execution.
        pass


def _load_provider_state() -> dict:
    if os.path.exists(PROVIDER_STATE_FILE):
        try:
            with open(PROVIDER_STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
    return {"last_good": None}


def _save_provider_state(last_good: str):
    try:
        os.makedirs(os.path.dirname(PROVIDER_STATE_FILE), exist_ok=True)
        with open(PROVIDER_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({"last_good": last_good, "updated": datetime.now().isoformat()}, f, indent=2)
    except Exception:
        pass


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


def _normalize_app_name(name: str) -> str:
    cleaned = re.sub(r"\s+", " ", name.strip().lower())
    return APP_ALIASES.get(cleaned, cleaned)


def _run_template_task(task_description: str) -> str | None:
    """Run deterministic task templates without requiring screenshot vision."""
    from tools.adb_control import open_app, type_text, press_enter, replay_task

    lower_task = task_description.lower().strip()

    replay_name = _extract_replay_name(task_description)
    if replay_name:
        msg = replay_task(replay_name)
        _trace("template_replay", task=task_description, replay_name=replay_name, result=msg[:200])
        return f"Done: replay '{replay_name}' — {msg}"

    pkg, app_name = _resolve_app_package(task_description)
    if any(k in lower_task for k in ["open ", "launch ", "play "]) and pkg:
        steps = [f"opened {app_name} ({pkg}) — {open_app(pkg)}"]

        if any(k in lower_task for k in ["search ", "type ", "write "]):
            payload = _extract_text_payload(task_description)
            if payload:
                steps.append(f"typed '{payload[:80]}' — {type_text(payload)}")
                steps.append(press_enter())

            _trace("template_open_search", task=task_description, app=app_name, package=pkg, typed=bool(payload if 'payload' in locals() else False))
            return "Done: " + " | ".join(steps)

    return None


def _load_key(name: str) -> str:
    with open("Keys.txt") as f:
        for line in f:
            if line.startswith(name):
                return line.split("=", 1)[1].strip()
    raise ValueError(f"{name} not found")


def _screenshot_via_flutter() -> tuple[str | None, str]:
    try:
        resp = requests.post(FLUTTER_URL, json={"action": "screenshot"}, timeout=10)
        data = resp.json()
        img_path = data.get("path")
        if img_path and os.path.exists(img_path):
            with open(img_path, "rb") as f:
                raw = f.read()
            if raw:
                return base64.b64encode(raw).decode(), "flutter"
        return None, "flutter:no_path"
    except Exception as e:
        return None, f"flutter:error:{e}"


def _screenshot_via_termux() -> tuple[str | None, str]:
    tmp_path = "/data/data/com.termux/files/home/lyra_vision_screen.png"
    try:
        subprocess.run(["termux-screenshot", "-f", tmp_path], capture_output=True, text=True, timeout=8)
        if os.path.exists(tmp_path):
            with open(tmp_path, "rb") as f:
                raw = f.read()
            if raw:
                return base64.b64encode(raw).decode(), "termux"
        return None, "termux:no_file"
    except Exception as e:
        return None, f"termux:error:{e}"


def _screenshot_via_screencap() -> tuple[str | None, str]:
    tmp_path = "/data/data/com.termux/files/home/lyra_vision_screen.png"
    for bin_name in ("screencap", "/system/bin/screencap"):
        try:
            subprocess.run([bin_name, "-p", tmp_path], capture_output=True, text=True, timeout=8)
            if os.path.exists(tmp_path):
                with open(tmp_path, "rb") as f:
                    raw = f.read()
                if raw:
                    return base64.b64encode(raw).decode(), f"native:{bin_name}"
        except Exception:
            continue
    return None, "native:failed"


def take_screenshot() -> tuple[str | None, str | None]:
    """Capture screenshot with provider fallback and cached last-known-good preference.

    Provider order defaults to:
    1) Flutter MediaProjection endpoint
    2) termux-screenshot
    3) native screencap
    """
    providers = [
        ("flutter", _screenshot_via_flutter),
        ("termux", _screenshot_via_termux),
        ("native", _screenshot_via_screencap),
    ]

    state = _load_provider_state()
    last_good = state.get("last_good")
    if last_good in {"flutter", "termux", "native"}:
        providers.sort(key=lambda p: 0 if p[0] == last_good else 1)

    errors = []
    for name, provider_fn in providers:
        img_b64, provider_tag = provider_fn()
        if img_b64:
            _save_provider_state(name)
            _trace("screenshot_ok", provider=name, provider_tag=provider_tag)
            return img_b64, name
        errors.append(provider_tag)

    _trace("screenshot_failed", errors=errors)
    return None, None


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

    # Prefer app target explicitly named after open/launch/play verbs.
    verb_match = re.search(r"\b(?:open|launch|play)\s+(.+?)(?:\s+and\s+|$)", lower)
    if verb_match:
        target = verb_match.group(1).strip()
        target = _normalize_app_name(target)
        for app_name in sorted(APP_PACKAGE_MAP.keys(), key=len, reverse=True):
            if app_name in target:
                return APP_PACKAGE_MAP[app_name], app_name

    # Prefer longer names first (e.g., "play store" before "play").
    normalized_full = _normalize_app_name(lower)
    for app_name in sorted(APP_PACKAGE_MAP.keys(), key=len, reverse=True):
        if app_name in normalized_full:
            return APP_PACKAGE_MAP[app_name], app_name
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

    _trace("task_start", task=task_description, max_steps=max_steps)

    template_result = _run_template_task(task_description)
    if template_result:
        _trace("task_done_template", task=task_description, result=template_result[:200])
        return template_result

    # Fast-path app launches for common "open/play app" tasks, independent of screenshot availability.
    lower_task = task_description.lower().strip()
    if any(k in lower_task for k in ["open ", "launch ", "play "]):
        pkg, app_name = _resolve_app_package(task_description)
        if pkg:
            open_result = open_app(pkg)
            _trace("task_done_fast_open", task=task_description, app=app_name, package=pkg, result=open_result[:120])
            return f"Done: opened {app_name} ({pkg}) — {open_result}"

    results = []
    for step in range(max_steps):
        screenshot, provider = take_screenshot()
        if not screenshot:
            # If screenshot path is unavailable, still try a package fallback for app-launch tasks.
            pkg, app_name = _resolve_app_package(task_description)
            if pkg:
                open_result = open_app(pkg)
                results.append(f"Done: fallback opened {app_name} ({pkg}) — {open_result}")
                _trace("task_done_fallback_open", task=task_description, app=app_name, package=pkg, result=open_result[:120])
                break
            return "Could not take screenshot — is Flutter running?"

        decision = analyze_screen(screenshot, task_description)
        action = decision.get("action", "done")
        reason = decision.get("reason", "")
        _trace("vision_decision", step=step + 1, provider=provider, action=action, reason=reason[:120])

        if decision.get("failed") or action == "failed":
            results.append(f"Failed: {reason}")
            _trace("task_failed", step=step + 1, reason=reason[:160])
            break

        if decision.get("done") or action == "done":
            results.append(f"Done: {reason}")
            _trace("task_done", step=step + 1, reason=reason[:160])
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
            _trace("task_unknown_action", step=step + 1, action=action, reason=reason[:120])
            break

        time.sleep(random.uniform(0.5, 1.5))

    final = "\n".join(results) if results else "No steps executed"
    _trace("task_end", task=task_description, result=final[:300])
    return final