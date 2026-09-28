"""Local SMTP catcher with a small browser inbox for Smart EV demos."""

from __future__ import annotations

import argparse
from collections import deque
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
from threading import Lock
from typing import Any
from urllib.parse import urlparse

from aiosmtpd.controller import Controller


MESSAGES: deque[dict[str, Any]] = deque(maxlen=100)
MESSAGES_LOCK = Lock()
URL_PATTERN = re.compile(r"https?://[^\s<>]+")


def _plain_body(message: Any) -> str:
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_type() == "text/plain" and not part.get_filename():
                return part.get_content()
        return ""
    return message.get_content()


def _linkify(value: str) -> str:
    parts: list[str] = []
    cursor = 0
    for match in URL_PATTERN.finditer(value):
        parts.append(escape(value[cursor:match.start()]))
        url = match.group(0).rstrip(".,;)")
        trailing = match.group(0)[len(url):]
        safe_url = escape(url, quote=True)
        parts.append(f'<a href="{safe_url}" target="_blank" rel="noreferrer">{safe_url}</a>')
        parts.append(escape(trailing))
        cursor = match.end()
    parts.append(escape(value[cursor:]))
    return "".join(parts)


class MailHandler:
    async def handle_DATA(self, server: Any, session: Any, envelope: Any) -> str:
        parsed = BytesParser(policy=policy.default).parsebytes(envelope.original_content)
        received_at = datetime.now(timezone.utc).isoformat()
        with MESSAGES_LOCK:
            message_id = (MESSAGES[0]["id"] + 1) if MESSAGES else 1
            MESSAGES.appendleft({
                "id": message_id,
                "from": str(parsed.get("From", envelope.mail_from)),
                "to": str(parsed.get("To", ", ".join(envelope.rcpt_tos))),
                "subject": str(parsed.get("Subject", "(no subject)")),
                "body": _plain_body(parsed),
                "received_at": received_at,
            })
        print(f"Captured email #{message_id}: {parsed.get('Subject', '(no subject)')}", flush=True)
        return "250 Message accepted for local demo"


def _page(title: str, content: str) -> bytes:
    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="5">
  <title>{escape(title)} · Smart EV Mail</title>
  <style>
    :root {{ color-scheme: dark; font-family: Inter, system-ui, sans-serif; }}
    body {{ margin: 0; background: #061711; color: #f4f8f5; }}
    main {{ width: min(980px, calc(100% - 32px)); margin: 42px auto; }}
    header {{ display: flex; align-items: center; justify-content: space-between; gap: 20px; margin-bottom: 24px; }}
    h1 {{ margin: 0; font-size: clamp(1.7rem, 5vw, 2.6rem); }}
    .badge {{ color: #43e495; background: #0b3023; padding: 8px 12px; border-radius: 999px; }}
    .card {{ display: block; color: inherit; text-decoration: none; border: 1px solid #24493b; background: #0d281f; border-radius: 16px; padding: 18px; margin: 12px 0; }}
    .card:hover {{ border-color: #43e495; }}
    .meta {{ color: #a9c8bc; font-size: .9rem; }}
    .subject {{ font-size: 1.12rem; font-weight: 700; margin: 8px 0; }}
    pre {{ white-space: pre-wrap; overflow-wrap: anywhere; font: inherit; line-height: 1.7; }}
    a {{ color: #43e495; }}
    .empty {{ padding: 48px; text-align: center; border: 1px dashed #315448; border-radius: 16px; color: #a9c8bc; }}
  </style>
</head>
<body><main>{content}</main></body>
</html>"""
    return document.encode("utf-8")


class InboxRequestHandler(BaseHTTPRequestHandler):
    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        route = urlparse(self.path).path
        with MESSAGES_LOCK:
            messages = list(MESSAGES)

        if route == "/api/messages":
            payload = json.dumps(messages, ensure_ascii=False).encode("utf-8")
            self._send(200, payload, "application/json; charset=utf-8")
            return

        if route.startswith("/message/"):
            try:
                message_id = int(route.rsplit("/", 1)[-1])
            except ValueError:
                self._send(404, b"Not found", "text/plain; charset=utf-8")
                return
            message = next((item for item in messages if item["id"] == message_id), None)
            if message is None:
                self._send(404, b"Not found", "text/plain; charset=utf-8")
                return
            content = f"""
<header><div><a href="/">← Inbox</a><h1>{escape(message['subject'])}</h1></div><span class="badge">Local demo</span></header>
<section class="card">
  <div class="meta">From: {escape(message['from'])}</div>
  <div class="meta">To: {escape(message['to'])}</div>
  <div class="meta">Received: {escape(message['received_at'])}</div>
  <pre>{_linkify(message['body'])}</pre>
</section>"""
            self._send(200, _page(message["subject"], content), "text/html; charset=utf-8")
            return

        if route != "/":
            self._send(404, b"Not found", "text/plain; charset=utf-8")
            return

        cards = "".join(
            f"""<a class="card" href="/message/{message['id']}">
  <div class="meta">To: {escape(message['to'])} · {escape(message['received_at'])}</div>
  <div class="subject">{escape(message['subject'])}</div>
  <div class="meta">{escape(message['body'][:140])}</div>
</a>"""
            for message in messages
        )
        if not cards:
            cards = '<div class="empty">No messages yet. Register an account or request a password reset.</div>'
        content = f"""
<header><div><div class="meta">SMART EV DEVELOPMENT TOOL</div><h1>Email inbox</h1></div><span class="badge">SMTP connected</span></header>
{cards}"""
        self._send(200, _page("Inbox", content), "text/html; charset=utf-8")

    def log_message(self, format: str, *args: Any) -> None:
        return


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Smart EV's local SMTP catcher and browser inbox.")
    parser.add_argument("--smtp-host", default="127.0.0.1")
    parser.add_argument("--smtp-port", type=int, default=1025)
    parser.add_argument("--http-host", default="127.0.0.1")
    parser.add_argument("--http-port", type=int, default=8025)
    args = parser.parse_args()

    smtp = Controller(MailHandler(), hostname=args.smtp_host, port=args.smtp_port)
    smtp.start()
    http = ThreadingHTTPServer((args.http_host, args.http_port), InboxRequestHandler)
    print(f"Smart EV SMTP listening at {args.smtp_host}:{args.smtp_port}", flush=True)
    print(f"Smart EV inbox: http://localhost:{args.http_port}", flush=True)
    try:
        http.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        http.server_close()
        smtp.stop()


if __name__ == "__main__":
    main()
