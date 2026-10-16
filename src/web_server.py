"""Serve a local browser interface for the voice assistant."""

from __future__ import annotations

import json
import re
import threading
from email.message import EmailMessage
import os
import smtplib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from assistant import CONFIG_PATH, VoiceAssistant

HOST, PORT = "127.0.0.1", int(os.getenv("PORT", "8000"))
PAGE = Path(__file__).with_name("index.html")


class WebAssistant(VoiceAssistant):
    def __init__(self):
        self.custom_commands = self._load_commands()
        self.messages = []
        self.lock = threading.RLock()
        self.pending_email = None

    def say(self, message: str) -> None:
        self.messages.append(message)

    def listen(self):
        # The browser collects email confirmation as a second command.
        return None

    def handle(self, utterance: str) -> bool:
        with self.lock:
            self.messages = []
            lowered = utterance.strip().lower()
            if self.pending_email:
                if re.search(r"\b(confirm|send it|yes)\b", lowered):
                    self._send_pending_email()
                elif re.search(r"\b(cancel|no)\b", lowered):
                    self.pending_email = None
                    self.say("Email cancelled.")
                else:
                    self.say("Please say confirm send email, or cancel.")
                return True
            super().handle(utterance)
            return True

    def _email(self, text: str) -> None:
        match = re.search(r"(?:send(?: an?)? (?:email|e-mail)|email|e-mail) to\s+(\S+@\S+)\s+subject\s+(.+?)\s+message\s+(.+)$", text, re.I)
        if not match:
            self.say("Say: send email to address@example.com subject Hello message Your message.")
            return
        self.pending_email = match.groups()
        recipient, subject, body = self.pending_email
        self.say(f"I heard an email to {recipient}, subject {subject}, with message: {body}. Say confirm send email to send it, or cancel.")

    def _send_pending_email(self):
        recipient, subject, body = self.pending_email
        self.pending_email = None
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


assistant = WebAssistant()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in ("/", "/index.html"):
            self.send_error(404)
            return
        content = PAGE.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self):
        if self.path != "/api/command":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 4000:
                raise ValueError("Command is empty or too long.")
            payload = json.loads(self.rfile.read(length))
            command = payload.get("command", "")
            if not isinstance(command, str) or not command.strip():
                raise ValueError("Please enter a command.")
            assistant.handle(command[:1000])
            body = json.dumps({"responses": assistant.messages}, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (ValueError, json.JSONDecodeError) as exc:
            body = json.dumps({"error": str(exc)}).encode("utf-8")
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, format, *args):
        print(f"{self.address_string()} - {format % args}")


if __name__ == "__main__":
    print(f"Voice Assistant is available at http://{HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
