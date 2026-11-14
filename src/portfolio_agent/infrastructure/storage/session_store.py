"""In-memory SessionStore: conversation turns and the last result table per session."""

import threading
from collections import OrderedDict

from portfolio_agent.application.schemas import Session


class InMemorySessionStore:
    def __init__(self, max_sessions: int = 1000) -> None:
        self._sessions: OrderedDict[str, Session] = OrderedDict()
        self._max_sessions = max_sessions
        self._lock = threading.Lock()

    def get(self, session_id: str) -> Session:
        with self._lock:
            session = self._sessions.get(session_id)
            return session.model_copy(deep=True) if session else Session()

    def save(self, session_id: str, session: Session) -> None:
        with self._lock:
            self._sessions[session_id] = session
            self._sessions.move_to_end(session_id)
            while len(self._sessions) > self._max_sessions:
                self._sessions.popitem(last=False)
