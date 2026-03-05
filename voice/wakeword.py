import pvporcupine
import pyaudio
import struct
import time

ACCESS_KEY = "7EfH7ISm/yrqkn8Ue/7m4G1RVMT0Afd/N/bNpD8Bi9meSbYjZRkQfg=="

def wait_for_wakeword():
    porcupine = pvporcupine.create(
        access_key=ACCESS_KEY,
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