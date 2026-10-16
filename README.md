# Voice Assistant

A Python desktop voice assistant that listens through a microphone, speaks responses aloud, handles common requests, opens web searches, schedules reminders, and optionally connects to a weather service and SMTP email server.

## Setup

Use Python 3.10 or newer. Install the dependencies:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

`PyAudio` requires a working microphone/audio setup and may need an OS-specific wheel or audio development package. `SpeechRecognition`'s Google recognizer sends recorded speech to Google's recognition service, so an internet connection is required for transcription. Text-to-speech is provided by the local `pyttsx3` engine.

Start the terminal assistant from the project directory:

```powershell
python src/assistant.py
```

To use the browser interface, start the local server instead:

```powershell
python src/web_server.py
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000). Use the text field or the **Speak** button. Browser speech recognition requires browser support and microphone permission; speech recognition happens in the browser. Responses are spoken by the browser. Stop the server with Ctrl+C. Set `PORT` to use a different port.

## Example requests

- “Hello”
- “What time is it?” / “What is today's date?”
- “Search for beginner Python tutorials”
- “Remind me in 10 minutes to check the oven”
- “What is the capital of France?” (local knowledge base)
- “What is the weather in Delhi?” (requires API key)
- “Send email to test@example.com subject Hello message This is a test” (requires SMTP settings and spoken confirmation)
- “Quit”

The intent parser recognizes natural phrasing through intent and entity patterns. It is intentionally small and does not use an LLM. For knowledge questions outside its bundled facts, ask it to search the web.

## Optional integrations

Weather: create a free OpenWeatherMap API key and set it as `OPENWEATHER_API_KEY`. Optionally set `WEATHER_CITY` to supply a default city. For example, in PowerShell:

```powershell
$env:OPENWEATHER_API_KEY = "your-key"
$env:WEATHER_CITY = "Delhi"
```

Email: configure `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, and `SMTP_FROM` in the process environment. Use a test mailbox or SMTP sandbox. `SMTP_SSL=true` selects implicit TLS; otherwise the client uses STARTTLS. Email requests are read back and must be confirmed before sending. Credentials are never stored in the project config.

## Custom commands

Edit `config/commands.json`. Each key is a phrase that should match in a spoken request. A command can say a response or open a URL:

```json
{
  "open python website": {
    "url": "https://www.python.org/",
    "response": "Opening the Python website."
  },
  "say hello there": {
    "response": "Hello there!"
  }
}
```

Alternatively set `ASSISTANT_CONFIG` to the path of a different JSON config file.

## Privacy

- Microphone audio is captured while the assistant is listening. Transcription uses `recognize_google`, which transmits audio to Google's speech recognition service; the assistant does not save recordings.
- Spoken queries used for web search are sent to Google Search in the browser.
- A requested weather city and API key are sent to OpenWeatherMap. Weather is not queried unless requested.
- Email recipient, subject, and message are sent through the SMTP server you configure, and only after spoken confirmation. Keep SMTP secrets in environment variables; do not commit them.
- Reminders and speech output run locally. Custom commands are read from the local JSON config.
- No conversation history is saved by this application.

## Limitations

The app needs a usable microphone and speakers. Speech transcription depends on network access and Google's recognition endpoint. The bundled question answering is a small local fact list, not general purpose QA. Timed reminders last only for the current process and are lost when the app exits. API/network failures are reported by voice.
