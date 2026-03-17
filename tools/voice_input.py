import os
import base64
import tempfile

from groq import Groq


def _load_key(name: str) -> str:
    with open("Keys.txt") as f:
        for line in f:
            if line.startswith(name):
                return line.split("=", 1)[1].strip()
    raise ValueError(f"{name} not found")


client = Groq(api_key=_load_key("GROQ"))


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
            result = transcription.strip() if isinstance(transcription, str) else str(transcription)
            return result
        finally:
            try:
                os.remove(tmp_path)
            except Exception:
                pass
    except Exception as e:
        return f"Transcription error: {e}"