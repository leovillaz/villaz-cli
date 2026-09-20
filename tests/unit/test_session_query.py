from dataclasses import (
    FrozenInstanceError,
    fields,
)
from datetime import datetime, timezone
from inspect import signature
from typing import Any

import pytest

import villaz_cli.session_query as session_query
from villaz_cli.conversation import (
    LogicalConversationHistory,
    Message,
    MessageRole,
    Turn,
)
from villaz_cli.session import (
    PersistenceMode,
    ProfileMode,
    ProfileModeKind,
    Session,
    SessionAuthority,
    SessionLifecycle,
    SessionSyncState,
)
from villaz_cli.session_persistence import (
    SessionIdentityMismatchError,
    SessionNotFoundError,
)
from villaz_cli.session_query import (
    SessionSummary,
    inspect_persisted_session,
    list_persisted_sessions,
    summarize_session,
)
from villaz_cli.session_state import (
    UnsupportedSessionSchemaError,
    session_to_state,
)


_CREATED_AT = datetime(
    2026,
    9,
    12,
    10,
    0,
    tzinfo=timezone.utc,
)

_UPDATED_AT = datetime(
    2026,
    9,
    12,
    11,
    0,
    tzinfo=timezone.utc,
)


class FakeSessionStateStore:
    def __init__(self) -> None:
        self.states: dict[str, dict[str, Any]] = {}
        self.save_calls = 0
        self.load_calls = 0
        self.list_calls = 0
        self.purge_calls = 0

    def save(
        self,
        *,
        session_id: str,
        state: dict[str, Any],
    ) -> None:
        self.save_calls += 1
        self.states[session_id] = state

    def load(
        self,
        *,
        session_id: str,
    ) -> dict[str, Any]:
        self.load_calls += 1

        try:
            return self.states[session_id]
        except KeyError as exc:
            raise SessionNotFoundError(
                f"Session não encontrada: {session_id}."
            ) from exc

    def list_session_ids(self) -> tuple[str, ...]:
        self.list_calls += 1
        return tuple(
            self.states
        )

    def purge(
        self,
        *,
        session_id: str,
    ) -> None:
        self.purge_calls += 1
        self.states.pop(
            session_id,
            None,
        )


def _session(
    session_id: str = "session-test",
    *,
    lifecycle: SessionLifecycle = SessionLifecycle.ACTIVE,
    profile_mode: ProfileMode | None = None,
    created_at: datetime = _CREATED_AT,
    updated_at: datetime = _UPDATED_AT,
    turn_count: int = 0,
) -> Session:
    conversation = LogicalConversationHistory()

    for index in range(
        turn_count
    ):
        conversation.append(
            Turn(
                user=Message(
                    role=MessageRole.USER,
                    content=f"conteúdo sensível user {index}",
                ),
                assistant=Message(
                    role=MessageRole.ASSISTANT,
                    content=f"conteúdo sensível assistant {index}",
                ),
            )
        )

    return Session(
        session_id=session_id,
        conversation=conversation,
        persistence_mode=PersistenceMode.PERSISTENT,
        authority=SessionAuthority.LOCAL,
        profile_mode=profile_mode or ProfileMode.auto(),
        created_at=created_at,
        updated_at=updated_at,
        lifecycle=lifecycle,
        sync_state=SessionSyncState.CLEAN,
    )


def _persist(
    store: FakeSessionStateStore,
    session: Session,
) -> None:
    store.states[
        session.session_id
    ] = session_to_state(
        session
    )


def test_session_summary_is_frozen_slots_and_has_exact_fields() -> None:
    summary = summarize_session(
        _session()
    )

    assert tuple(
        field.name
        for field in fields(
            SessionSummary
        )
    ) == (
        "session_id",
        "lifecycle",
        "persistence_mode",
        "authority",
        "profile_mode",
        "created_at",
        "updated_at",
        "turn_count",
    )

    assert not hasattr(
        summary,
        "__dict__",
    )

    with pytest.raises(
        FrozenInstanceError,
    ):
        summary.turn_count = 99


def test_summarize_session_projects_approved_metadata() -> None:
    session = _session(
        session_id="session-summary",
        turn_count=2,
    )

    summary = summarize_session(
        session
    )

    assert summary.session_id == "session-summary"
    assert summary.lifecycle is SessionLifecycle.ACTIVE
    assert summary.persistence_mode is PersistenceMode.PERSISTENT
    assert summary.authority is SessionAuthority.LOCAL
    assert summary.created_at == _CREATED_AT
    assert summary.updated_at == _UPDATED_AT
    assert summary.turn_count == 2


def test_summarize_session_does_not_expose_conversation_content() -> None:
    summary = summarize_session(
        _session(
            turn_count=2,
        )
    )

    field_names = {
        field.name
        for field in fields(
            SessionSummary
        )
    }

    assert "conversation" not in field_names
    assert "turns" not in field_names
    assert "content" not in field_names

    rendered = repr(
        summary
    )

    assert "conteúdo sensível" not in rendered


def test_summarize_session_preserves_auto_profile() -> None:
    summary = summarize_session(
        _session()
    )

    assert summary.profile_mode.kind is ProfileModeKind.AUTO
    assert summary.profile_mode.profile_id is None


def test_summarize_session_preserves_explicit_profile() -> None:
    profile_mode = ProfileMode.explicit(
        "code-review-security"
    )

    summary = summarize_session(
        _session(
            profile_mode=profile_mode,
        )
    )

    assert summary.profile_mode == profile_mode
    assert summary.profile_mode.kind is ProfileModeKind.EXPLICIT
    assert (
        summary.profile_mode.profile_id
        == "code-review-security"
    )


@pytest.mark.parametrize(
    "lifecycle",
    [
        SessionLifecycle.ACTIVE,
        SessionLifecycle.CLOSED,
        SessionLifecycle.DELETED,
    ],
)
def test_summarize_session_preserves_lifecycle(
    lifecycle: SessionLifecycle,
) -> None:
    summary = summarize_session(
        _session(
            lifecycle=lifecycle,
        )
    )

    assert summary.lifecycle is lifecycle


def test_list_empty_returns_empty_tuple() -> None:
    store = FakeSessionStateStore()

    result = list_persisted_sessions(
        store=store,
    )

    assert result == ()
    assert store.list_calls == 1
    assert store.load_calls == 0


def test_list_loads_all_sessions_and_orders_updated_at_desc() -> None:
    store = FakeSessionStateStore()

    oldest = _session(
        "session-old",
        updated_at=datetime(
            2026,
            9,
            12,
            8,
            0,
            tzinfo=timezone.utc,
        ),
    )
    newest = _session(
        "session-new",
        updated_at=datetime(
            2026,
            9,
            12,
            12,
            0,
            tzinfo=timezone.utc,
        ),
    )
    middle = _session(
        "session-middle",
        updated_at=datetime(
            2026,
            9,
            12,
            10,
            0,
            tzinfo=timezone.utc,
        ),
    )

    _persist(
        store,
        oldest,
    )
    _persist(
        store,
        newest,
    )
    _persist(
        store,
        middle,
    )

    result = list_persisted_sessions(
        store=store,
    )

    assert tuple(
        summary.session_id
        for summary in result
    ) == (
        "session-new",
        "session-middle",
        "session-old",
    )

    assert store.load_calls == 3


def test_list_uses_session_id_ascending_as_tiebreaker() -> None:
    store = FakeSessionStateStore()

    same_time = datetime(
        2026,
        9,
        12,
        12,
        30,
        tzinfo=timezone.utc,
    )

    _persist(
        store,
        _session(
            "session-c",
            updated_at=same_time,
        ),
    )
    _persist(
        store,
        _session(
            "session-a",
            updated_at=same_time,
        ),
    )
    _persist(
        store,
        _session(
            "session-b",
            updated_at=same_time,
        ),
    )

    result = list_persisted_sessions(
        store=store,
    )

    assert tuple(
        summary.session_id
        for summary in result
    ) == (
        "session-a",
        "session-b",
        "session-c",
    )


def test_list_keeps_deleted_sessions_visible() -> None:
    store = FakeSessionStateStore()

    deleted = _session(
        "session-deleted",
        lifecycle=SessionLifecycle.DELETED,
    )

    _persist(
        store,
        deleted,
    )

    result = list_persisted_sessions(
        store=store,
    )

    assert len(result) == 1
    assert result[0].session_id == "session-deleted"
    assert result[0].lifecycle is SessionLifecycle.DELETED


def test_inspect_returns_summary_not_session() -> None:
    store = FakeSessionStateStore()

    persisted = _session(
        "session-inspect",
        turn_count=1,
    )

    _persist(
        store,
        persisted,
    )

    result = inspect_persisted_session(
        "session-inspect",
        store=store,
    )

    assert isinstance(
        result,
        SessionSummary,
    )
    assert not isinstance(
        result,
        Session,
    )
    assert result.session_id == "session-inspect"
    assert result.turn_count == 1


def test_inspect_missing_session_propagates_existing_error() -> None:
    store = FakeSessionStateStore()

    with pytest.raises(
        SessionNotFoundError,
        match="não encontrada",
    ):
        inspect_persisted_session(
            "missing-session",
            store=store,
        )


def test_inspect_invalid_schema_propagates_existing_error() -> None:
    store = FakeSessionStateStore()

    state = session_to_state(
        _session(
            "session-invalid",
        )
    )
    state["schema_version"] = 999

    store.states[
        "session-invalid"
    ] = state

    with pytest.raises(
        UnsupportedSessionSchemaError,
        match="não suportado",
    ):
        inspect_persisted_session(
            "session-invalid",
            store=store,
        )


def test_inspect_identity_mismatch_propagates_existing_error() -> None:
    store = FakeSessionStateStore()

    store.states[
        "requested-session"
    ] = session_to_state(
        _session(
            "different-session",
        )
    )

    with pytest.raises(
        SessionIdentityMismatchError,
        match="identidade",
    ):
        inspect_persisted_session(
            "requested-session",
            store=store,
        )


def test_list_is_read_only() -> None:
    store = FakeSessionStateStore()

    _persist(
        store,
        _session(
            "session-read-only",
        ),
    )

    list_persisted_sessions(
        store=store,
    )

    assert store.save_calls == 0
    assert store.purge_calls == 0


def test_inspect_is_read_only() -> None:
    store = FakeSessionStateStore()

    _persist(
        store,
        _session(
            "session-read-only",
        ),
    )

    inspect_persisted_session(
        "session-read-only",
        store=store,
    )

    assert store.save_calls == 0
    assert store.purge_calls == 0


def test_query_api_has_no_lock_dependency() -> None:
    list_parameters = signature(
        list_persisted_sessions
    ).parameters
    inspect_parameters = signature(
        inspect_persisted_session
    ).parameters

    assert "lock_store" not in list_parameters
    assert "lock_store" not in inspect_parameters

    assert not hasattr(
        session_query,
        "acquire_session_lock",
    )
    assert not hasattr(
        session_query,
        "release_session_lock",
    )
