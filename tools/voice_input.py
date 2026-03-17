import os
import subprocess
import base64
import tempfile
from groq import Groq

AUDIO_PATH = "/data/data/com.termux/files/home/lyra_voice.mp3"
RECORD_SECONDS = 6


def _load_key(name: str) -> str:
    with open("Keys.txt") as f:
        for line in f:
            if line.startswith(name):
                return line.split("=", 1)[1].strip()
    raise ValueError(f"{name} not found")


client = Groq(api_key=_load_key("GROQ"))


def record_and_transcribe() -> str:
    try:
        if os.path.exists(AUDIO_PATH):
            os.remove(AUDIO_PATH)
        # Correct flag order: -d first, then -f, then -l
        subprocess.run(
            ["termux-microphone-record", "-d", "-f", AUDIO_PATH, "-l", str(RECORD_SECONDS)],
            timeout=RECORD_SECONDS + 5
        )
        if not os.path.exists(AUDIO_PATH) or os.path.getsize(AUDIO_PATH) < 100:
            return "Recording failed — no audio captured"
        with open(AUDIO_PATH, "rb") as f:
            transcription = client.audio.transcriptions.create(
                file=("audio.mp3", f.read()),
                model="whisper-large-v3",
                language="en",
                response_format="text"
            )
        result = transcription.strip() if isinstance(transcription, str) else str(transcription)
        return result
    except Exception as e:
        return f"Transcription error: {e}"
    finally:
        try:
            os.remove(AUDIO_PATH)
        except Exception:
            pass


def transcribe_base64(audio_b64: str, ext: str = "mp4") -> str:
    try:
        audio_bytes = base64.b64decode(audio_b64)
        tmp_path = os.path.join(tempfile.gettempdir(), f"lyra_audio.{ext}")
        with open(tmp_path, "wb") as f:
            f.write(audio_bytes)
        try:
            with open(tmp_path, "rb") as f:
                transcription = client.audio.transcriptions.create(
                    file=(f"audio.{ext}", f.read()),
                    model="whisper-large-v3",
                    language="en",
                    response_format="text"
                )
            return transcription.strip() if isinstance(transcription, str) else str(transcription)
        finally:
            try:
                os.remove(tmp_path)
            except Exception:
                pass
    except Exception as e:
        return f"Transcription error: {e}"