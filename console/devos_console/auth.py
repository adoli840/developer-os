from __future__ import annotations

import hmac
import secrets
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from http.cookies import SimpleCookie
from threading import Lock


SESSION_COOKIE = "devos_session"
SESSION_TTL_SECONDS = 8 * 60 * 60


@dataclass(frozen=True)
class Session:
    session_id: str
    csrf_token: str
    expires_at: float


class SessionStore:
    def __init__(
        self,
        access_token: str,
        *,
        secure_cookie: bool,
        cookie_name: str = SESSION_COOKIE,
        cookie_path: str = "/",
    ) -> None:
        self._access_token = access_token
        self._secure_cookie = secure_cookie
        self._cookie_name = cookie_name
        self._cookie_path = cookie_path
        self._sessions: dict[str, Session] = {}
        self._attempts: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def login(self, token: str, remote_address: str) -> Session | None:
        now = time.time()
        with self._lock:
            attempts = self._attempts[remote_address]
            while attempts and attempts[0] < now - 60:
                attempts.popleft()
            if len(attempts) >= 8:
                return None
            attempts.append(now)

        if not self._access_token or not hmac.compare_digest(token, self._access_token):
            return None
        session = self._create_session(now)
        with self._lock:
            self._attempts.pop(remote_address, None)
        return session

    def create_trusted(self) -> Session:
        return self._create_session(time.time())

    def _create_session(self, now: float) -> Session:
        session = Session(
            session_id=secrets.token_urlsafe(32),
            csrf_token=secrets.token_urlsafe(24),
            expires_at=now + SESSION_TTL_SECONDS,
        )
        with self._lock:
            self._sessions[session.session_id] = session
        return session

    def from_cookie(self, cookie_header: str | None) -> Session | None:
        if not cookie_header:
            return None
        cookie = SimpleCookie()
        try:
            cookie.load(cookie_header)
        except Exception:
            return None
        value = cookie.get(self._cookie_name)
        if value is None:
            return None
        now = time.time()
        with self._lock:
            session = self._sessions.get(value.value)
            if session is None:
                return None
            if session.expires_at <= now:
                self._sessions.pop(session.session_id, None)
                return None
            return session

    def logout(self, session: Session) -> None:
        with self._lock:
            self._sessions.pop(session.session_id, None)

    def cookie_header(self, session: Session) -> str:
        secure = "; Secure" if self._secure_cookie else ""
        return (
            f"{self._cookie_name}={session.session_id}; Path={self._cookie_path}; HttpOnly; "
            f"SameSite=Strict; Max-Age={SESSION_TTL_SECONDS}{secure}"
        )

    def expired_cookie_header(self) -> str:
        return (
            f"{self._cookie_name}=; Path={self._cookie_path}; HttpOnly; "
            "SameSite=Strict; Max-Age=0"
        )
