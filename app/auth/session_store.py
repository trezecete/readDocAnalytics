from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from fastapi import Request, Response
from itsdangerous import BadSignature, URLSafeSerializer

from app.config import Settings


@dataclass
class Session:
    session_id: str
    data: dict[str, Any]
    is_new: bool = False


class SessionStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._serializer = URLSafeSerializer(
            settings.session_secret,
            salt="read-doc-analytics-session",
        )
        self._sessions: dict[str, dict[str, Any]] = {}

    def get_or_create(self, request: Request) -> Session:
        signed_id = request.cookies.get(self.settings.session_cookie_name)
        session_id = self._decode_session_id(signed_id) if signed_id else None
        if not session_id or session_id not in self._sessions:
            session_id = uuid4().hex
            self._sessions[session_id] = {}
            return Session(session_id=session_id, data=self._sessions[session_id], is_new=True)
        return Session(session_id=session_id, data=self._sessions[session_id])

    def save(self, response: Response, session: Session) -> None:
        signed_id = self._serializer.dumps(session.session_id)
        response.set_cookie(
            self.settings.session_cookie_name,
            signed_id,
            httponly=True,
            secure=self.settings.cookie_secure,
            samesite="lax",
            max_age=60 * 60,
        )

    def destroy(self, response: Response, session: Session) -> None:
        self._sessions.pop(session.session_id, None)
        response.delete_cookie(self.settings.session_cookie_name)

    def _decode_session_id(self, signed_id: str | None) -> str | None:
        if not signed_id:
            return None
        try:
            value = self._serializer.loads(signed_id)
        except BadSignature:
            return None
        return value if isinstance(value, str) else None

