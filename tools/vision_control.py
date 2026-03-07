import os
import json
import base64
import re
import time
from groq import Groq

VISION_MODEL = "llama-3.2-90b-vision-preview"
COMMAND_FILE = "/sdcard/Download/lyra_cmd.json"
RESULT_FILE = "/sdcard/Download/lyra_result.json"

def _load_key(name: str) -> str:
    with open("Keys.txt", "r") as f:
        for line in f:
            if line.startswith(name):
                return line.split("=", 1)[1].strip()
    raise ValueError(f"{name} key not found in Keys.txt")

client = Groq(api_key=_load_key("GROQ"))

def take_screenshot() -> str:
    # Clean old files
    for f in [COMMAND_FILE, RESULT_FILE]:
        if os.path.exists(f):
            os.remove(f)

    # Write command for Flutter
    with open(COMMAND_FILE, "w") as f:
        json.dump({"action": "screenshot"}, f)

    # Wait for Flutter to respond (max 15 seconds)
    for _ in range(30):
        time.sleep(0.5)
        if os.path.exists(RESULT_FILE):
            with open(RESULT_FILE, "r") as f:
                result = json.load(f)
            os.remove(RESULT_FILE)
            if result.get("status") == "ok":
                return result.get("path")
            else:
                print(f"[Vision] {result.get('message', 'Unknown error')}")
                return None

    print("[Vision] Flutter did not respond in time. Is Lyra app open?")
    return None

def _image_to_base64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

def analyze_screen(prompt: str = None) -> str:
    path = take_screenshot()
    if not path:
        return "Couldn't take screenshot. Make sure the Lyra app is open on your phone."

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
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_base64}"}}
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
        if os.path.exists(path):
            try:
                os.remove(path)
            except:
                pass

def read_screen() -> str:
    return analyze_screen("Read and transcribe ALL text visible on this screen. Return the text exactly as shown. Do not describe the UI, just give me the text content.")

def describe_screen() -> str:
    return analyze_screen("What app is open and what is the user looking at? Describe briefly — what screen is this, what content is visible, what state is it in. Be concise, 2-3 sentences max.")

def analyze_screen_with_question(question: str) -> str:
    return analyze_screen(f"Look at this screenshot and answer this question: {question}")