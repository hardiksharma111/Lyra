import speech_recognition as sr
import pyttsx3

def speak(text: str):
    engine = pyttsx3.init()
    engine.say(text)
    engine.runAndWait()
    engine.stop()

def listen() -> str:
    recognizer = sr.Recognizer()

    # Higher threshold = only processes clearer speech
    # Reduces false triggers from background noise
    recognizer.energy_threshold = 4000
    recognizer.dynamic_energy_threshold = True

    with sr.Microphone() as source:
        print("Listening...")
        recognizer.adjust_for_ambient_noise(source, duration=0.3)
        audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)

    try:
        text = recognizer.recognize_google(audio)
        print(f"You said: {text}")
        return text

    except sr.UnknownValueError:
        return "I couldn't understand that"

    except sr.RequestError:
        return "Speech service unavailable"

    except sr.WaitTimeoutError:
        return "No speech detected"