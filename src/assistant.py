"""A small, privacy-conscious voice assistant for the terminal."""

from __future__ import annotations

import json
import os
import re
import smtplib
import threading
import webbrowser
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import quote_plus

try:
    import pyttsx3
    import speech_recognition as sr
except ImportError as exc:
    raise SystemExit("Install dependencies with: python -m pip install -r requirements.txt") from exc

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = Path(os.getenv("ASSISTANT_CONFIG", ROOT / "config" / "commands.json"))


class VoiceAssistant:
    def __init__(self) -> None:
        self.recognizer = sr.Recognizer()
        self.speech_lock = threading.Lock()
        self.engine = pyttsx3.init()
        self.engine.setProperty("rate", 175)
        self.custom_commands = self._load_commands()

    @staticmethod
    def _load_commands() -> dict:
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def say(self, message: str) -> None:
        print(f"Assistant: {message}")
        with self.speech_lock:
            self.engine.say(message)
            self.engine.runAndWait()

    def listen(self) -> str | None:
        try:
            with sr.Microphone() as source:
                print("Listening…")
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = self.recognizer.listen(source, timeout=8, phrase_time_limit=12)
            return self.recognizer.recognize_google(audio).strip()
        except sr.WaitTimeoutError:
            self.say("I didn't hear anything. Please repeat your request.")
        except sr.UnknownValueError:
            self.say("I couldn't understand that. Please repeat your request.")
        except sr.RequestError:
            self.say("Speech recognition is unavailable. Check your internet connection and try again.")
        except (OSError, AttributeError) as exc:
            self.say(f"I couldn't access the microphone: {exc}")
        return None

    def handle(self, utterance: str) -> bool:
        text = utterance.strip()
        lower = text.lower()
        if not text:
            self.say("Please repeat your request.")
            return True
        if re.search(r"\b(exit|quit|goodbye|stop listening)\b", lower):
            self.say("Goodbye!")
            return False
        if self._custom(text):
            return True
        if re.search(r"\b(hello|hi|hey)\b", lower):
            self.say("Hello! How can I help you?")
        elif re.search(r"\b(time|date|day)\b", lower):
            now = datetime.now().astimezone()
            if "time" in lower and not re.search(r"\b(date|day)\b", lower):
                self.say(f"It is {now.strftime('%I:%M %p')}.")
            elif "time" in lower:
                self.say(f"It is {now.strftime('%I:%M %p')} on {now.strftime('%A, %B %d, %Y')}.")
            else:
                self.say(f"Today is {now.strftime('%A, %B %d, %Y')}.")
        elif self._reminder(text):
            pass
        elif re.search(r"\b(weather|forecast)\b", lower):
            self._weather(text)
        elif re.search(r"\b(email|e-mail)\b", lower):
            self._email(text)
        elif re.search(r"\b(who|what|where|when|why|how)\b", lower) and not re.search(r"\b(search|google|look up)\b", lower):
            self._answer(text)
        elif re.search(r"\b(search|google|look up|find)\b", lower):
            query = re.sub(r"^(please\s+)?(search for|search|google|look up|find)\s*", "", text, flags=re.I).strip()
            query = re.sub(r"\s+on the web$", "", query, flags=re.I)
            if query:
                webbrowser.open("https://www.google.com/search?q=" + quote_plus(query))
                self.say(f"Searching the web for {query}.")
            else:
                self.say("What would you like me to search for?")
        else:
            self.say("I didn't recognize that request. You can ask for the time, weather, a reminder, or a web search.")
        return True

    def _custom(self, text: str) -> bool:
        for phrase, action in self.custom_commands.items():
            if phrase.lower() in text.lower() and isinstance(action, dict):
                if action.get("url"):
                    webbrowser.open(str(action["url"]))
                    self.say(action.get("response", f"Opening {phrase}."))
                elif action.get("response"):
                    self.say(str(action["response"]))
                else:
                    self.say("That custom command has no action configured.")
                return True
        return False

    def _reminder(self, text: str) -> bool:
        match = re.search(r"\bremind me in\s+(\d+)\s*(seconds?|minutes?|hours?)\s*(?:to\s+)?(.*)", text, re.I)
        if not match:
            return False
        amount, unit, reminder = match.groups()
        multiplier = 3600 if unit.lower().startswith("hour") else 60 if unit.lower().startswith("minute") else 1
        delay = int(amount) * multiplier
        if delay < 1 or delay > 7 * 24 * 3600:
            self.say("Please choose a reminder between one second and seven days.")
            return True
        note = reminder.strip() or "your reminder"
        threading.Timer(delay, self.say, args=(f"Reminder: {note}.",)).start()
        self.say(f"Okay, I'll remind you in {amount} {unit} to {note}.")
        return True

    def _weather(self, text: str) -> None:
        city = re.sub(r"\b(weather|forecast|in|for|what is|what's|the)\b", " ", text, flags=re.I)
        city = " ".join(city.split()).strip(" ?.,") or os.getenv("WEATHER_CITY", "")
        key = os.getenv("OPENWEATHER_API_KEY")
        if not key:
            self.say("Weather needs an OpenWeatherMap API key. Set OPENWEATHER_API_KEY in your environment.")
            return
        if not city:
            self.say("Which city should I check?")
            return
        try:
            from urllib.request import urlopen
            from urllib.error import URLError
            url = f"https://api.openweathermap.org/data/2.5/weather?q={quote_plus(city)}&appid={quote_plus(key)}&units=metric"
            with urlopen(url, timeout=8) as response:
                data = json.loads(response.read().decode("utf-8"))
            description = data["weather"][0]["description"]
            self.say(f"In {data['name']}, it's {description}, {round(data['main']['temp'])} degrees Celsius, with humidity at {data['main']['humidity']} percent.")
        except Exception:
            self.say("I couldn't fetch the weather. Check the city and API key, then try again.")

    def _email(self, text: str) -> None:
        match = re.search(r"(?:send(?: an?)? (?:email|e-mail)|email|e-mail) to\s+(\S+@\S+)\s+subject\s+(.+?)\s+message\s+(.+)$", text, re.I)
        if not match:
            self.say("Say: send email to address@example.com subject project update message Your message here.")
            return
        recipient, subject, body = match.groups()
        self.say(f"I heard an email to {recipient}, subject {subject}, with message: {body}. Say confirm send email to send it, or say cancel.")
        confirmation = self.listen()
        if not confirmation or not re.search(r"\bconfirm\b", confirmation, re.I):
            self.say("Email cancelled.")
            return
        host, user, password, sender = (os.getenv(k) for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM"))
        if not all((host, user, password, sender)):
            self.say("Email sending is not configured. Set SMTP_HOST, SMTP_USER, SMTP_PASSWORD, and SMTP_FROM.")
            return
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = sender, recipient, subject
        msg.set_content(body)
        try:
            port = int(os.getenv("SMTP_PORT", "587"))
            if os.getenv("SMTP_SSL", "false").lower() == "true":
                with smtplib.SMTP_SSL(host, port, timeout=15) as server:
                    server.login(user, password)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(host, port, timeout=15) as server:
                    server.starttls()
                    server.login(user, password)
                    server.send_message(msg)
            self.say("Email sent.")
        except (OSError, smtplib.SMTPException, ValueError):
            self.say("I couldn't send the email. Check your SMTP settings.")

    def _answer(self, text: str) -> None:
        question = text.lower().strip(" ?.!\t")
        answers = {
            "what is the capital of france": "Paris is the capital of France.",
            "who wrote hamlet": "William Shakespeare wrote Hamlet.",
            "what is the largest planet": "Jupiter is the largest planet in our solar system.",
            "how many days are in a week": "There are seven days in a week.",
            "what is the boiling point of water": "Water boils at 100 degrees Celsius at sea level.",
        }
        response = answers.get(question)
        if response:
            self.say(response)
        else:
            self.say("I don't know that one. I can search the web if you say search for, followed by your question.")

    def run(self) -> None:
        self.say("Voice assistant is ready. Say hello, ask a question, or say quit to exit.")
        running = True
        while running:
            utterance = self.listen()
            if utterance is not None:
                running = self.handle(utterance)


if __name__ == "__main__":
    try:
        VoiceAssistant().run()
    except KeyboardInterrupt:
        print("\nAssistant stopped.")
