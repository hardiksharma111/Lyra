import os
import socket
import json
import base64
import re
from groq import Groq

VISION_MODEL = "llama-3.2-90b-vision-preview"
FLUTTER_HOST = "127.0.0.1"
FLUTTER_PORT = 5001

def _load_key(name: str) -> str:
    with open("Keys.txt", "r") as f:
        for line in f:
            if line.startswith(name):
                return line.split("=", 1)[1].strip()
    raise ValueError(f"{name} key not found in Keys.txt")

client = Groq(api_key=_load_key("GROQ"))

def _send_command(command: dict) -> dict:
    """Send command to Flutter app via socket and get response."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(15)
        sock.connect((FLUTTER_HOST, FLUTTER_PORT))

        message = json.dumps(command) + "\n"
        sock.sendall(message.encode("utf-8"))

        response_data = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response_data += chunk
            if b"\n" in response_data:
                break

        sock.close()

        response_text = response_data.decode("utf-8").strip()
        if response_text:
            return json.loads(response_text)
        return {"status": "error", "message": "Empty response from Flutter"}

    except ConnectionRefusedError:
        return {"status": "error", "message": "Flutter app not running. Open Lyra app on phone first."}
    except socket.timeout:
        return {"status": "error", "message": "Flutter app timed out"}
    except Exception as e:
        return {"status": "error", "message": f"Socket error: {e}"}

def take_screenshot() -> str:
    """Request screenshot from Flutter app. Returns path or None."""
    result = _send_command({"action": "screenshot"})
    if result.get("status") == "ok":
        return result.get("path")
    print(f"[Vision] {result.get('message', 'Unknown error')}")
    return None

def _image_to_base64(path: str) -> str:
    """Convert image file to base64 string."""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

def analyze_screen(prompt: str = None) -> str:
    """Take screenshot via Flutter and analyze with vision model."""
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
        # Clean up screenshot after processing
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass

def read_screen() -> str:
    """Read all visible text on screen."""
    return analyze_screen("Read and transcribe ALL text visible on this screen. Return the text exactly as shown, preserving the layout as much as possible. Do not describe the UI, just give me the text content.")

def describe_screen() -> str:
    """Describe what app/screen is showing."""
    return analyze_screen("What app is open and what is the user looking at? Describe briefly — what screen is this, what content is visible, what state is it in. Be concise, 2-3 sentences max.")

def analyze_screen_with_question(question: str) -> str:
    """Answer a specific question about what's on screen."""
    return analyze_screen(f"Look at this screenshot and answer this question: {question}")
