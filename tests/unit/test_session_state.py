from datetime import datetime, timezone

import pytest

from villaz_cli.conversation import (
    LogicalConversationHistory,
    Message,
    MessageRole,
    Turn,
)
from villaz_cli.session import (
    PersistenceMode,
    ProfileMode,
    Session,
    SessionAuthority,
    SessionLifecycle,
    SessionSyncState,
)
from villaz_cli.session_state import (
    SESSION_SCHEMA_VERSION,
    SessionStateError,
    UnsupportedSessionSchemaError,
    session_from_state,
    session_to_state,
)


_CREATED_AT = datetime(
    2026,
    9,
    11,
    18,
    0,
    tzinfo=timezone.utc,
)

_UPDATED_AT = datetime(
    2026,
    9,
    11,
    18,
    30,
    tzinfo=timezone.utc,
)


def _history() -> LogicalConversationHistory:
    history = LogicalConversationHistory()

    history.append(
        Turn(
            user=Message(
                role=MessageRole.USER,
                content="primeira pergunta",
            ),
            assistant=Message(
                role=MessageRole.ASSISTANT,
                content="primeira resposta",
            ),
        )
    )

    history.append(
        Turn(
            user=Message(
                role=MessageRole.USER,
                content="segunda pergunta",
            ),
            assistant=Message(
                role=MessageRole.ASSISTANT,
                content="segunda resposta",
            ),
        )
    )

    return history


def _persistent_session(
    *,
    lifecycle: SessionLifecycle = SessionLifecycle.ACTIVE,
    authority: SessionAuthority = SessionAuthority.LOCAL,
    profile_mode: ProfileMode | None = None,
    sync_state: SessionSyncState = SessionSyncState.CLEAN,
) -> Session:
    return Session(
        session_id="session-test",
        conversation=_history(),
        persistence_mode=PersistenceMode.PERSISTENT,
        authority=authority,
        profile_mode=profile_mode or ProfileMode.auto(),
        created_at=_CREATED_AT,
        updated_at=_UPDATED_AT,
        lifecycle=lifecycle,
        sync_state=sync_state,
    )


def test_schema_version_starts_at_one() -> None:
    assert SESSION_SCHEMA_VERSION == 1


def test_session_to_state_serializes_complete_logical_state() -> None:
    session = _persistent_session(
        lifecycle=SessionLifecycle.CLOSED,
        authority=SessionAuthority.REMOTE,
        profile_mode=ProfileMode.explicit(
            "code-review-security"
        ),
        sync_state=SessionSyncState.DIRTY,
    )

    state = session_to_state(session)

    assert state["schema_version"] == SESSION_SCHEMA_VERSION
    assert state["session_id"] == "session-test"
    assert state["lifecycle"] == "closed"
    assert state["persistence_mode"] == "persistent"
    assert state["authority"] == "remote"
    assert state["profile_mode"] == {
        "kind": "explicit",
        "profile_id": "code-review-security",
    }
    assert state["created_at"] == _CREATED_AT.isoformat()
    assert state["updated_at"] == _UPDATED_AT.isoformat()
    assert state["conversation"] == {
        "turns": [
            {
                "user": {
                    "role": "user",
                    "content": "primeira pergunta",
                },
                "assistant": {
                    "role": "assistant",
                    "content": "primeira resposta",
                },
            },
            {
                "user": {
                    "role": "user",
                    "content": "segunda pergunta",
                },
                "assistant": {
                    "role": "assistant",
                    "content": "segunda resposta",
                },
            },
        ]
    }


def test_session_to_state_does_not_persist_sync_state() -> None:
    session = _persistent_session(
        sync_state=SessionSyncState.DIRTY,
    )

    state = session_to_state(session)

    assert "sync_state" not in state


def test_ephemeral_session_cannot_generate_persisted_state() -> None:
    session = Session(
        session_id="ephemeral-session",
        conversation=LogicalConversationHistory(),
        persistence_mode=PersistenceMode.EPHEMERAL,
        authority=SessionAuthority.LOCAL,
        profile_mode=ProfileMode.auto(),
        created_at=_CREATED_AT,
        updated_at=_CREATED_AT,
    )

    with pytest.raises(
        SessionStateError,
        match="PERSISTENT",
    ):
        session_to_state(session)


def test_session_round_trip_preserves_state() -> None:
    original = _persistent_session(
        lifecycle=SessionLifecycle.CLOSED,
        authority=SessionAuthority.REMOTE,
        profile_mode=ProfileMode.explicit(
            "code-review-security"
        ),
        sync_state=SessionSyncState.DIRTY,
    )

    restored = session_from_state(
        session_to_state(original)
    )

    assert restored.session_id == original.session_id
    assert restored.lifecycle is original.lifecycle
    assert restored.persistence_mode is original.persistence_mode
    assert restored.authority is original.authority
    assert restored.profile_mode == original.profile_mode
    assert restored.created_at == original.created_at
    assert restored.updated_at == original.updated_at
    assert restored.conversation.turns == original.conversation.turns


def test_restored_session_starts_clean() -> None:
    original = _persistent_session(
        sync_state=SessionSyncState.DIRTY,
    )

    restored = session_from_state(
        session_to_state(original)
    )

    assert restored.sync_state is SessionSyncState.CLEAN


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        "invalid",
        123,
    ],
)
def test_root_payload_must_be_object(
    payload: object,
) -> None:
    with pytest.raises(
        SessionStateError,
        match="raiz",
    ):
        session_from_state(payload)


@pytest.mark.parametrize(
    "schema_version",
    [
        None,
        "1",
        True,
    ],
)
def test_schema_version_must_be_exact_integer(
    schema_version: object,
) -> None:
    payload = session_to_state(
        _persistent_session()
    )
    payload["schema_version"] = schema_version

    with pytest.raises(
        SessionStateError,
        match="schema_version",
    ):
        session_from_state(payload)


@pytest.mark.parametrize(
    "schema_version",
    [
        0,
        2,
        999,
    ],
)
def test_unsupported_schema_version_is_rejected(
    schema_version: int,
) -> None:
    payload = session_to_state(
        _persistent_session()
    )
    payload["schema_version"] = schema_version

    with pytest.raises(
        UnsupportedSessionSchemaError,
        match="não suportado",
    ):
        session_from_state(payload)


def test_persisted_session_must_be_persistent() -> None:
    payload = session_to_state(
        _persistent_session()
    )
    payload["persistence_mode"] = "ephemeral"

    with pytest.raises(
        SessionStateError,
        match="PERSISTENT",
    ):
        session_from_state(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("session_id", None),
        ("session_id", 123),
        ("lifecycle", None),
        ("persistence_mode", None),
        ("authority", None),
        ("created_at", None),
        ("updated_at", None),
    ],
)
def test_required_scalar_fields_are_validated(
    field: str,
    value: object,
) -> None:
    payload = session_to_state(
        _persistent_session()
    )
    payload[field] = value

    with pytest.raises(SessionStateError):
        session_from_state(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("lifecycle", "paused"),
        ("persistence_mode", "unknown"),
        ("authority", "hybrid"),
    ],
)
def test_unknown_enum_values_are_rejected(
    field: str,
    value: str,
) -> None:
    payload = session_to_state(
        _persistent_session()
    )
    payload[field] = value

    with pytest.raises(SessionStateError):
        session_from_state(payload)


def test_invalid_datetime_is_rejected() -> None:
    payload = session_to_state(
        _persistent_session()
    )
    payload["updated_at"] = "not-a-datetime"

    with pytest.raises(
        SessionStateError,
        match="datetime",
    ):
        session_from_state(payload)


def test_invalid_profile_mode_is_rejected() -> None:
    payload = session_to_state(
        _persistent_session()
    )
    payload["profile_mode"] = {
        "kind": "explicit",
        "profile_id": None,
    }

    with pytest.raises(
        SessionStateError,
        match="profile mode",
    ):
        session_from_state(payload)


def test_unknown_message_role_is_rejected() -> None:
    payload = session_to_state(
        _persistent_session()
    )

    payload["conversation"]["turns"][0]["user"]["role"] = "system"

    with pytest.raises(
        SessionStateError,
        match="role",
    ):
        session_from_state(payload)


def test_swapped_message_role_is_rejected() -> None:
    payload = session_to_state(
        _persistent_session()
    )

    payload["conversation"]["turns"][0]["user"]["role"] = "assistant"

    with pytest.raises(
        SessionStateError,
        match="role",
    ):
        session_from_state(payload)


def test_non_list_turns_are_rejected() -> None:
    payload = session_to_state(
        _persistent_session()
    )

    payload["conversation"]["turns"] = {}

    with pytest.raises(
        SessionStateError,
        match="turns",
    ):
        session_from_state(payload)


def test_invalid_turn_shape_is_rejected_without_partial_session() -> None:
    payload = session_to_state(
        _persistent_session()
    )

    payload["conversation"]["turns"][1] = {
        "user": {
            "role": "user",
            "content": "incompleta",
        }
    }

    with pytest.raises(SessionStateError):
        session_from_state(payload)
