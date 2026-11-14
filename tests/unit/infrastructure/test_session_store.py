"""Tests for session state and the in-memory session store."""

from portfolio_agent.application.schemas import MAX_SESSION_TURNS, Session, Table, Turn
from portfolio_agent.infrastructure.storage.session_store import InMemorySessionStore

TABLE = Table(columns=["a"], rows=[{"a": 1}], source="qa")


def turn(i: int) -> Turn:
    return Turn(request=f"q{i}", workflow="qa", status="ok", summary=f"a{i}")


def test_new_session_is_empty() -> None:
    assert InMemorySessionStore().get("nope") == Session()


def test_saved_session_is_returned_as_a_copy() -> None:
    store = InMemorySessionStore()
    store.save("s1", Session().with_turn(turn(1), TABLE))
    loaded = store.get("s1")
    loaded.turns.clear()
    assert len(store.get("s1").turns) == 1


def test_turns_are_capped() -> None:
    session = Session()
    for i in range(MAX_SESSION_TURNS + 5):
        session = session.with_turn(turn(i), None)
    assert len(session.turns) == MAX_SESSION_TURNS
    assert session.turns[-1].request == f"q{MAX_SESSION_TURNS + 4}"


def test_last_table_kept_when_turn_has_none() -> None:
    session = Session().with_turn(turn(1), TABLE).with_turn(turn(2), None)
    assert session.last_table == TABLE


def test_oldest_sessions_evicted() -> None:
    store = InMemorySessionStore(max_sessions=2)
    for sid in ("a", "b", "c"):
        store.save(sid, Session().with_turn(turn(1), None))
    assert store.get("a") == Session()
    assert store.get("c").turns
