import os
import sys
import json
import time
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

# Add current directory to path to ensure imports work from CWD
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.agent import Agent
from logs.session import start_session
from core.mood_engine import detect_mood, get_time_context
from memory.pattern_engine import get_all_categories

# Instantiate global agent and session
agent = Agent()
session_id = start_session()
agent.set_session(session_id)

PORT = 5000
WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")

class LyraWebHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Silence default terminal logs to keep output clean, unless debug is enabled
        if agent.debug:
            sys.stderr.write("%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), format%args))

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        # API Endpoints
        if path == "/api/status":
            self.handle_api_status()
        elif path == "/api/memory":
            self.handle_api_memory()
        else:
            # Static file serving
            self.handle_static_files(path)

    def do_POST(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        if path == "/api/chat":
            self.handle_api_chat()
        else:
            self.send_error_response(404, "Not Found")

    def handle_static_files(self, path):
        # Landing page at root
        if path == "/" or path == "/landing.html":
            file_path = os.path.join(WEB_DIR, "landing.html")
        # Chat app at /app
        elif path == "/app" or path == "/app/" or path == "/index.html":
            file_path = os.path.join(WEB_DIR, "index.html")
        else:
            # Strip leading slash and prevent directory traversal
            clean_path = os.path.normpath(path.lstrip("/"))
            if clean_path.startswith("..") or os.path.isabs(clean_path):
                self.send_error_response(403, "Access Denied")
                return
            file_path = os.path.join(WEB_DIR, clean_path)

        if not os.path.exists(file_path) or os.path.isdir(file_path):
            # Fallback to index.html for SPA behavior or return 404
            if path.startswith("/api/"):
                self.send_error_response(404, "API Endpoint Not Found")
            else:
                self.send_error_response(404, f"File {path} Not Found")
            return

        # Content Types mapping
        content_types = {
            ".html": "text/html",
            ".css": "text/css",
            ".js": "application/javascript",
            ".json": "application/json",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".svg": "image/svg+xml",
            ".ico": "image/x-icon"
        }
        _, ext = os.path.splitext(file_path)
        content_type = content_types.get(ext.lower(), "application/octet-stream")

        try:
            with open(file_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error_response(500, f"Internal Server Error: {str(e)}")

    def handle_api_status(self):
        # Check Baileys whatsapp connection
        baileys_connected = False
        try:
            import requests
            r = requests.post("http://127.0.0.1:5003", json={"action": "status"}, timeout=1)
            baileys_connected = r.json().get("connected", False)
        except Exception:
            pass

        # Check OAuth integrations
        services = {
            "spotify": os.path.exists("memory/spotify_token.json") or os.path.exists(".cache"),
            "gmail": os.path.exists("memory/gmail_token.json"),
            "classroom": os.path.exists("memory/classroom_token.json"),
            "whatsapp": baileys_connected
        }

        # Find current mood based on conversation history or default to casual
        last_user_msg = next((m["content"] for m in reversed(agent.conversation_history) if m["role"] == "user"), "")
        current_mood = detect_mood(last_user_msg) if last_user_msg else "casual"

        data = {
            "status": "ok",
            "model": agent.model,
            "debug": agent.debug,
            "mood": current_mood,
            "time": get_time_context(),
            "services": services
        }
        self.send_json_response(data)

    def handle_api_memory(self):
        try:
            categories = get_all_categories()
            # If categories returns list of categories, package it
            data = {
                "status": "ok",
                "categories": categories
            }
            self.send_json_response(data)
        except Exception as e:
            self.send_json_response({"status": "error", "error": str(e)})

    def handle_api_chat(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            payload = json.loads(post_data.decode("utf-8"))
            message = payload.get("message", "").strip()

            if not message:
                self.send_json_response({"status": "error", "error": "Empty message"})
                return

            # Call Agent think loop
            response_text = agent.think(message)

            # Detect mood based on the user prompt we just processed
            mood = detect_mood(message)

            # Determine if voice should speak (if not a system command or quiet mode)
            speak_audio = True
            if any(message.lower().strip().startswith(cmd) for cmd in [
                "debug", "suggestions", "errors", "pending", "reminders", "benchmark"
            ]):
                speak_audio = False

            data = {
                "status": "ok",
                "response": response_text,
                "mood": mood,
                "time": get_time_context(),
                "speak": speak_audio
            }
            self.send_json_response(data)

        except Exception as e:
            self.send_json_response({"status": "error", "error": str(e)})

    def send_json_response(self, data):
        try:
            content = json.dumps(data).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error_response(500, f"Error serializing JSON: {str(e)}")

    def send_error_response(self, code, message):
        response_data = {"status": "error", "error": message}
        content = json.dumps(response_data).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

def run_server():
    server_address = ("", PORT)
    httpd = HTTPServer(server_address, LyraWebHandler)
    print(f"==================================================")
    print(f" Lyra Web Client Server running at http://localhost:{PORT}")
    print(f" Press Ctrl+C to terminate.")
    print(f"==================================================")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down web server...")
        httpd.server_close()

if __name__ == "__main__":
    # Ensure Keys.txt is present
    if not os.path.exists("Keys.txt"):
        print("Error: Keys.txt not found in the root directory.")
        sys.exit(1)

    # Ensure web folder exists
    if not os.path.exists(WEB_DIR):
        print(f"Error: web directory not found at {WEB_DIR}.")
        sys.exit(1)

    run_server()
