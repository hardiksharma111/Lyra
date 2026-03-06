import os
import subprocess
import base64
import json
import re
from groq import Groq

VISION_MODEL = "llama-3.2-90b-vision-preview"
SCREENSHOT_PATH = os.path.expanduser("~/screenshot_temp.png")

def _load_key(name: str) -> str:
    with open("Keys.txt", "r") as f:
        for line in f:
            if line.startswith(name):
                return line.split("=", 1)[1].strip()
    raise ValueError(f"{name} key not found in Keys.txt")

client = Groq(api_key=_load_key("GROQ"))

def take_screenshot() -> str:
    """Take screenshot on Android. Returns path or None."""
    # Clean up old screenshot
    if os.path.exists(SCREENSHOT_PATH):
        os.remove(SCREENSHOT_PATH)

    # Method 1: termux-screenshot (needs Termux:API)
    try:
        result = subprocess.run(
            ["termux-screenshot", SCREENSHOT_PATH],
            capture_output=True, text=True, timeout=10
        )
        if os.path.exists(SCREENSHOT_PATH):
            return SCREENSHOT_PATH
    except Exception:
        pass

    # Method 2: screencap (built-in Android, may need root)
    try:
        result = subprocess.run(
            ["screencap", "-p", SCREENSHOT_PATH],
            capture_output=True, text=True, timeout=10
        )
        if os.path.exists(SCREENSHOT_PATH):
            return SCREENSHOT_PATH
    except Exception:
        pass

    return None

def _image_to_base64(path: str) -> str:
    """Convert image file to base64 string."""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

def analyze_screen(prompt: str = None) -> str:
    """Take screenshot and analyze with vision model."""
    path = take_screenshot()
    if not path:
        return "Couldn't take screenshot. Make sure Termux:API is installed — run: pkg install termux-api"

    if not prompt:
        prompt = "Describe what is on this screen. Be concise and focus on the main content visible."

    try:
        img_base64 = _image_to_base64(path)

        response = client.chat.completions.create(
            model=VISION_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{img_base64}"
                        }
                    }
                ]
            }],
            max_tokens=1000
        )

        result = response.choices[0].message.content.strip()
        result = re.sub(r'\*+', '', result)
        result = re.sub(r'#+\s', '', result)
        result = ' '.join(result.split())
        return result

    except Exception as e:
        return f"Vision error: {e}"
    finally:
        # Always clean up screenshot after processing
        if os.path.exists(path):
            os.remove(path)

def read_screen() -> str:
    """Read all visible text on screen."""
    return analyze_screen("Read and transcribe ALL text visible on this screen. Return the text exactly as shown, preserving the layout as much as possible. Do not describe the UI, just give me the text content.")

def describe_screen() -> str:
    """Describe what app/screen is showing."""
    return analyze_screen("What app is open and what is the user looking at? Describe briefly — what screen is this, what content is visible, what state is it in. Be concise, 2-3 sentences max.")

def analyze_screen_with_question(question: str) -> str:
    """Answer a specific question about what's on screen."""
    return analyze_screen(f"Look at this screenshot and answer this question: {question}")git add .
git commit -m "session 3 - computer vision via groq"
git push