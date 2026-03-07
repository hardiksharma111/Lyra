import os
import json
import base64
import re
import requests
from groq import Groq

VISION_MODEL = "llama-3.2-90b-vision-preview"
FLUTTER_URL = "http://127.0.0.1:5001/command"
REQUEST_TIMEOUT = 15

def _load_key(name: str) -> str:
    with open("Keys.txt", "r") as f:
        for line in f:
            if line.startswith(name):
                return line.split("=", 1)[1].strip()
    raise ValueError(f"{name} key not found in Keys.txt")

client = Groq(api_key=_load_key("GROQ"))

def _send_command(command: dict) -> dict:
    """Send command to Flutter via HTTP POST."""
    try:
        response = requests.post(
            FLUTTER_URL,
            json=command,
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        return {"status": "error", "message": "Flutter app not running. Open Lyra app on phone first."}
    except requests.exceptions.Timeout:
        return {"status": "error", "message": "Flutter app timed out."}
    except Exception as e:
        return {"status": "error", "message": f"HTTP error: {e}"}

def _clean_text(text: str) -> str:
    text = re.sub(r'\*+', '', text)
    text = re.sub(r'#+\s', '', text)
    text = ' '.join(text.split())
    return text.strip()

def _analyze_image(path: str, prompt: str) -> str:
    """Send screenshot to Groq vision model."""
    try:
        with open(path, "rb") as f:
            img_base64 = base64.b64encode(f.read()).decode("utf-8")
        response = client.chat.completions.create(
            model=VISION_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_base64}"}}
                ]
            }],
            max_tokens=1000
        )
        return _clean_text(response.choices[0].message.content.strip())
    except Exception as e:
        return f"Vision error: {e}"
    finally:
        try:
            os.remove(path)
        except:
            pass

def read_screen() -> str:
    """
    Primary: Use accessibility service — returns structured text instantly, no API call.
    Fallback: Screenshot → Groq vision.
    """
    result = _send_command({"action": "read_screen"})

    if result.get("status") != "ok":
        return result.get("message", "Could not read screen.")

    source = result.get("source", "unknown")

    # Accessibility path — structured text, free, instant
    if source == "accessibility":
        data = result.get("data", {})
        if data.get("status") != "ok":
            return data.get("message", "Accessibility service not active.")
        app = data.get("app", "Unknown app")
        full_text = data.get("full_text", "").strip()
        if not full_text:
            return f"{app} is open but no readable text found on screen."
        return f"[{app}] {full_text}"

    # Screenshot fallback — costs a Groq vision API call
    if source == "screenshot":
        path = result.get("path")
        if not path:
            return "Screenshot path missing."
        return _analyze_image(
            path,
            "Read and transcribe ALL text visible on this screen. Return the text exactly as shown, no descriptions."
        )

    return "Unknown response from Flutter."

def describe_screen() -> str:
    """Describe what app/screen is open."""
    result = _send_command({"action": "read_screen"})

    if result.get("status") != "ok":
        return result.get("message", "Could not read screen.")

    source = result.get("source", "unknown")

    if source == "accessibility":
        data = result.get("data", {})
        if data.get("status") != "ok":
            return data.get("message", "Accessibility service not active.")
        app = data.get("app", "Unknown app")
        full_text = data.get("full_text", "").strip()
        if not full_text:
            return f"{app} is open, no visible text content."
        # Summarize with Groq — text only, no vision API needed
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{
                    "role": "user",
                    "content": f"The user has {app} open. Here's the screen text: {full_text[:2000]}\n\nDescribe briefly what they're looking at in 1-2 sentences."
                }],
                max_tokens=150
            )
            return _clean_text(response.choices[0].message.content.strip())
        except:
            return f"{app} is open. Content: {full_text[:300]}"

    if source == "screenshot":
        path = result.get("path")
        if not path:
            return "Screenshot path missing."
        return _analyze_image(
            path,
            "What app is open and what is the user looking at? Describe briefly in 1-2 sentences."
        )

    return "Unknown response from Flutter."

def analyze_screen() -> str:
    """Full screen analysis — accessibility text + optional vision."""
    return read_screen()

def analyze_screen_with_question(question: str) -> str:
    """Answer a specific question about what's on screen."""
    result = _send_command({"action": "read_screen"})

    if result.get("status") != "ok":
        return result.get("message", "Could not read screen.")

    source = result.get("source", "unknown")

    if source == "accessibility":
        data = result.get("data", {})
        if data.get("status") != "ok":
            return data.get("message", "Accessibility service not active.")
        app = data.get("app", "Unknown app")
        full_text = data.get("full_text", "").strip()
        if not full_text:
            return f"{app} is open but no readable text found."
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{
                    "role": "user",
                    "content": f"App open: {app}\nScreen text: {full_text[:2000]}\n\nQuestion: {question}\n\nAnswer directly and briefly."
                }],
                max_tokens=300
            )
            return _clean_text(response.choices[0].message.content.strip())
        except Exception as e:
            return f"Could not analyze: {e}"

    if source == "screenshot":
        path = result.get("path")
        if not path:
            return "Screenshot path missing."
        return _analyze_image(path, question)

    return "Unknown response from Flutter."