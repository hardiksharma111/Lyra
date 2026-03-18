import os
import subprocess
import base64
import tempfile
import wave
from groq import Groq

AUDIO_PATH = "/data/data/com.termux/files/home/lyra_voice.mp3"
RECORD_SECONDS = 6

SAMPLE_RATE = 16000
FRAME_DURATION_MS = 30
FRAME_SIZE = int(SAMPLE_RATE * FRAME_DURATION_MS / 1000)  # 480 samples
SILENCE_THRESHOLD = 50  # frames = 1.5 seconds
MAX_FRAMES = 1000  # 30 second cap
VAD_AGGRESSIVENESS = 2  # 0-3
VAD_AUDIO_PATH = "/data/data/com.termux/files/home/lyra_voice.wav"


def _load_key(name: str) -> str:
    with open("Keys.txt") as f:
        for line in f:
            if line.startswith(name):
                return line.split("=", 1)[1].strip()
    raise ValueError(f"{name} not found")


client = Groq(api_key=_load_key("GROQ"))

def start_vad_recording() -> str:
    try:
        import webrtcvad
        import pyaudio
    except Exception as e:
        raise RuntimeError(f"VAD deps missing: {e}")

    vad = webrtcvad.Vad(VAD_AGGRESSIVENESS)
    pa = pyaudio.PyAudio()
    stream = None
    frames: list[bytes] = []

    try:
        stream = pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=FRAME_SIZE,
        )

        state = "WAITING_FOR_SPEECH"
        silence_count = 0
        collected = 0

        for _ in range(MAX_FRAMES):
            data = stream.read(FRAME_SIZE, exception_on_overflow=False)
            is_speech = vad.is_speech(data, SAMPLE_RATE)

            if state == "WAITING_FOR_SPEECH":
                if is_speech:
                    state = "SPEAKING"
                    frames.append(data)
                    collected += 1
                    silence_count = 0
                continue

            if state == "SPEAKING":
                frames.append(data)
                collected += 1
                if is_speech:
                    silence_count = 0
                else:
                    silence_count += 1
                    if silence_count > SILENCE_THRESHOLD:
                        break

        if collected == 0 or len(frames) < 3:
            return "Recording failed — no speech detected"

        try:
            if os.path.exists(VAD_AUDIO_PATH):
                os.remove(VAD_AUDIO_PATH)
        except Exception:
            pass

        with wave.open(VAD_AUDIO_PATH, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(b"".join(frames))

        with open(VAD_AUDIO_PATH, "rb") as f:
            transcription = client.audio.transcriptions.create(
                file=("audio.wav", f.read()),
                model="whisper-large-v3",
                language="en",
                response_format="text",
            )

        return transcription.strip() if isinstance(transcription, str) else str(transcription).strip()
    finally:
        try:
            if stream is not None:
                stream.stop_stream()
                stream.close()
        except Exception:
            pass
        try:
            pa.terminate()
        except Exception:
            pass
        try:
            os.remove(VAD_AUDIO_PATH)
        except Exception:
            pass


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