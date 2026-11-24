"""Serve one interview round to the person's own browser and wait for the answers.

Each invocation owns one ephemeral loopback listener and one round key. The listener stops
after saving the answers or when its wait ends.
"""

from __future__ import annotations

import hmac
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Optional
from urllib.parse import parse_qs, urlsplit

HOST = "127.0.0.1"
KEY_HEADER = "X-Trackbed-Key"
MAX_BODY_BYTES = 256 * 1024
Check = Callable[[Any], "tuple[Optional[dict[str, Any]], list[str]]"]
SaveAnswers = Callable[[dict[str, Any]], None]


class RoundServer(ThreadingHTTPServer):
    """One round offered on the loopback address."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        key: str,
        page: str,
        policy: str,
        check: Check,
        save_answers: SaveAnswers,
    ):
        super().__init__((HOST, 0), Handler)
        self.key = key
        self.page = page.encode("utf-8")
        self.policy = policy
        self.check = check
        self.save_answers = save_answers
        self.answers: Optional[dict[str, Any]] = None
        self.submission_lock = threading.Lock()
        self.done = threading.Event()

    @property
    def port(self) -> int:
        return int(self.server_address[1])

    @property
    def url(self) -> str:
        return f"http://{HOST}:{self.port}/?k={self.key}"


class Handler(BaseHTTPRequestHandler):
    server: RoundServer
    server_version = "trackbed-interview"
    sys_version = ""
    protocol_version = "HTTP/1.1"
    # A connection that sends nothing must not hold a thread open.
    timeout = 15

    def log_message(self, format: str, *args: Any) -> None:
        """The helper's own output is the record; requests are not logged."""

    def _send(self, status: int, body: bytes, content_type: str, extra: Optional[dict[str, str]] = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Connection", "close")
        for name, value in (extra or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True

    def _json(self, status: int, value: dict[str, Any]) -> None:
        self._send(status, json.dumps(value).encode("utf-8"), "application/json; charset=utf-8")

    def _refuse(self, status: int, message: str) -> None:
        self._send(status, (message + "\n").encode("utf-8"), "text/plain; charset=utf-8")

    def _named_this_host(self) -> bool:
        """Refuse a request that reached the loopback address under another name."""
        port = self.server.port
        return self.headers.get("Host", "") in (f"{HOST}:{port}", f"localhost:{port}")

    def _keyed(self, given: str) -> bool:
        return hmac.compare_digest(given.encode("utf-8"), self.server.key.encode("utf-8"))

    def do_GET(self) -> None:
        if not self._named_this_host():
            self._refuse(403, "This address is not the interview page's own.")
            return
        target = urlsplit(self.path)
        if target.path != "/":
            self._refuse(404, "Nothing here.")
            return
        if not self._keyed((parse_qs(target.query).get("k") or [""])[0]):
            self._refuse(403, "This link is missing its key. Open the link the agent gave you.")
            return
        headers = {"Content-Security-Policy": self.server.policy + "; frame-ancestors 'none'"}
        self._send(200, self.server.page, "text/html; charset=utf-8", headers)

    def do_POST(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            length = -1
        if not 0 < length <= MAX_BODY_BYTES:
            self._refuse(413, "The answers are missing or too large.")
            return
        # Read before refusing: a reply sent over an unread request can be lost with the connection.
        body = self.rfile.read(length)
        origins = (f"http://{HOST}:{self.server.port}", f"http://localhost:{self.server.port}")
        if not self._named_this_host() or self.headers.get("Origin", origins[0]) not in origins:
            self._refuse(403, "Answers are accepted only from the interview page itself.")
            return
        if urlsplit(self.path).path != "/answers":
            self._refuse(404, "Nothing here.")
            return
        if not self._keyed(self.headers.get(KEY_HEADER, "")):
            self._refuse(403, "The round key is missing or wrong.")
            return
        if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
            self._refuse(415, "Answers must be sent as JSON.")
            return
        try:
            raw = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._json(422, {"ok": False, "problems": ["answers: are not valid JSON"]})
            return
        answers, problems = self.server.check(raw)
        if answers is None:
            self._json(422, {"ok": False, "problems": problems})
            return
        with self.server.submission_lock:
            if self.server.done.is_set():
                message = "this round was already answered" if self.server.answers is not None else "the wait ended"
                self._json(409, {"ok": False, "problems": [f"answers: {message}"]})
                return
            try:
                self.server.save_answers(answers)
            except OSError:
                self._json(500, {"ok": False, "problems": ["Could not save your answers. Try again or copy them."]})
                return
            self.server.answers = answers
            try:
                self._json(200, {"ok": True})
            finally:
                self.server.done.set()


def serve(server: RoundServer, expires_at: int, announce: Callable[[RoundServer], None]) -> Optional[dict[str, Any]]:
    """Serve until the round is answered or the wait runs out; the answers, or None."""
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True)
    thread.start()
    try:
        announce(server)
        server.done.wait(max(0.0, expires_at / 1000 - time.time()))
    finally:
        with server.submission_lock:
            server.done.set()
        server.shutdown()
        server.server_close()
        thread.join(5)
    return server.answers
