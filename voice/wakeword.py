import pvporcupine
import pyaudio
import struct
import time

def _load_key() -> str:
    with open("Keys.txt", "r") as f:
        for line in f:
            if line.startswith("PICOVOICE"):
                return line.split("=", 1)[1].strip()
    raise ValueError("PICOVOICE key not found in Keys.txt")

def wait_for_wakeword():
    porcupine = pvporcupine.create(
        access_key=_load_key(),
        keywords=["blueberry"]
    )

    pa = pyaudio.PyAudio()

    audio_stream = pa.open(
        rate=porcupine.sample_rate,
        channels=1,
        format=pyaudio.paInt16,
        input=True,
        frames_per_buffer=porcupine.frame_length
    )

    try:
        while True:
            pcm = audio_stream.read(porcupine.frame_length)
            pcm = struct.unpack_from("h" * porcupine.frame_length, pcm)
            keyword_index = porcupine.process(pcm)

            if keyword_index >= 0:
                audio_stream.close()
                pa.terminate()
                porcupine.delete()
                time.sleep(0.5)
                return True

    except Exception as e:
        return False

    finally:
        try:
            audio_stream.close()
            pa.terminate()
            porcupine.delete()
        except:
            pass