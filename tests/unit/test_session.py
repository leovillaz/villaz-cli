from datetime import datetime, timezone

import pytest

from villaz_cli.conversation import (
    ConversationResult,
    EffectiveInferenceContext,
    LogicalConversationHistory,
    Message,
    MessageRole,
    Turn,
)
from villaz_cli.session import (
    ConversationRequest,
    PersistenceMode,
    ProfileMode,
    ProfileModeKind,
    Session,
    SessionAuthority,
    SessionLifecycle,
    SessionLifecycleError,
    SessionSyncState,
    commit_conversation_result,
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
    1,
    tzinfo=timezone.utc,
)


def _session(
    *,
    lifecycle: SessionLifecycle = SessionLifecycle.ACTIVE,
    persistence_mode: PersistenceMode = PersistenceMode.EPHEMERAL,
    authority: SessionAuthority = SessionAuthority.LOCAL,
    profile_mode: ProfileMode | None = None,
    sync_state: SessionSyncState = SessionSyncState.CLEAN,
) -> Session:
    return Session(
        session_id="session-test",
        conversation=LogicalConversationHistory(),
        persistence_mode=persistence_mode,
        authority=authority,
        profile_mode=profile_mode or ProfileMode.auto(),
        created_at=_CREATED_AT,
        updated_at=_CREATED_AT,
        lifecycle=lifecycle,
        sync_state=sync_state,
    )


def _append_turn(session: Session) -> None:
    session.conversation.append(
        Turn(
            user=Message(
                role=MessageRole.USER,
                content="mensagem",
            ),
            assistant=Message(
                role=MessageRole.ASSISTANT,
                content="resposta",
            ),
        )
    )


def test_auto_profile_mode_has_no_profile_id() -> None:
    mode = ProfileMode.auto()

    assert mode.kind is ProfileModeKind.AUTO
    assert mode.profile_id is None


def test_explicit_profile_mode_preserves_profile_id() -> None:
    mode = ProfileMode.explicit("code-review-security")

    assert mode.kind is ProfileModeKind.EXPLICIT
    assert mode.profile_id == "code-review-security"


def test_auto_profile_mode_rejects_profile_id() -> None:
    with pytest.raises(
        ValueError,
        match="AUTO",
    ):
        ProfileMode(
            kind=ProfileModeKind.AUTO,
            profile_id="code-review-security",
        )


@pytest.mark.parametrize(
    "profile_id",
    [
        "",
        "   ",
    ],
)
def test_explicit_profile_mode_rejects_empty_profile_id(
    profile_id: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="EXPLICIT",
    ):
        ProfileMode.explicit(profile_id)


def test_session_preserves_identity_modes_and_timestamps() -> None:
    profile_mode = ProfileMode.explicit("code-review-security")

    session = _session(
        persistence_mode=PersistenceMode.PERSISTENT,
        authority=SessionAuthority.REMOTE,
        profile_mode=profile_mode,
    )

    assert session.session_id == "session-test"
    assert session.persistence_mode is PersistenceMode.PERSISTENT
    assert session.authority is SessionAuthority.REMOTE
    assert session.profile_mode == profile_mode
    assert session.created_at == _CREATED_AT
    assert session.updated_at == _CREATED_AT
    assert session.lifecycle is SessionLifecycle.ACTIVE
    assert session.sync_state is SessionSyncState.CLEAN


def test_ephemeral_session_rejects_dirty_state() -> None:
    with pytest.raises(
        ValueError,
        match="EPHEMERAL",
    ):
        _session(
            persistence_mode=PersistenceMode.EPHEMERAL,
            sync_state=SessionSyncState.DIRTY,
        )


def test_active_ephemeral_session_can_close() -> None:
    session = _session()

    session.close(updated_at=_UPDATED_AT)

    assert session.lifecycle is SessionLifecycle.CLOSED
    assert session.updated_at == _UPDATED_AT
    assert session.sync_state is SessionSyncState.CLEAN


def test_active_persistent_session_close_marks_dirty() -> None:
    session = _session(
        persistence_mode=PersistenceMode.PERSISTENT,
    )

    session.close(updated_at=_UPDATED_AT)

    assert session.lifecycle is SessionLifecycle.CLOSED
    assert session.updated_at == _UPDATED_AT
    assert session.sync_state is SessionSyncState.DIRTY


def test_closed_persistent_session_can_resume() -> None:
    session = _session(
        lifecycle=SessionLifecycle.CLOSED,
        persistence_mode=PersistenceMode.PERSISTENT,
    )

    session.resume(updated_at=_UPDATED_AT)

    assert session.lifecycle is SessionLifecycle.ACTIVE
    assert session.session_id == "session-test"
    assert session.updated_at == _UPDATED_AT
    assert session.sync_state is SessionSyncState.DIRTY


@pytest.mark.parametrize(
    "lifecycle",
    [
        SessionLifecycle.CLOSED,
        SessionLifecycle.DELETED,
    ],
)
def test_non_active_session_cannot_close(
    lifecycle: SessionLifecycle,
) -> None:
    session = _session(lifecycle=lifecycle)
    original_updated_at = session.updated_at

    with pytest.raises(SessionLifecycleError):
        session.close(updated_at=_UPDATED_AT)

    assert session.lifecycle is lifecycle
    assert session.updated_at == original_updated_at
    assert session.sync_state is SessionSyncState.CLEAN


@pytest.mark.parametrize(
    "lifecycle",
    [
        SessionLifecycle.ACTIVE,
        SessionLifecycle.DELETED,
    ],
)
def test_non_closed_session_cannot_resume(
    lifecycle: SessionLifecycle,
) -> None:
    session = _session(lifecycle=lifecycle)
    original_updated_at = session.updated_at

    with pytest.raises(SessionLifecycleError):
        session.resume(updated_at=_UPDATED_AT)

    assert session.lifecycle is lifecycle
    assert session.updated_at == original_updated_at
    assert session.sync_state is SessionSyncState.CLEAN


@pytest.mark.parametrize(
    "lifecycle",
    [
        SessionLifecycle.ACTIVE,
        SessionLifecycle.CLOSED,
    ],
)
def test_active_or_closed_persistent_session_can_be_deleted(
    lifecycle: SessionLifecycle,
) -> None:
    session = _session(
        lifecycle=lifecycle,
        persistence_mode=PersistenceMode.PERSISTENT,
    )

    session.delete(updated_at=_UPDATED_AT)

    assert session.lifecycle is SessionLifecycle.DELETED
    assert session.updated_at == _UPDATED_AT
    assert session.sync_state is SessionSyncState.DIRTY


def test_deleted_session_cannot_be_deleted_again() -> None:
    session = _session(
        lifecycle=SessionLifecycle.DELETED,
        persistence_mode=PersistenceMode.PERSISTENT,
    )
    original_updated_at = session.updated_at

    with pytest.raises(SessionLifecycleError):
        session.delete(updated_at=_UPDATED_AT)

    assert session.lifecycle is SessionLifecycle.DELETED
    assert session.updated_at == original_updated_at
    assert session.sync_state is SessionSyncState.CLEAN


def test_lifecycle_changes_preserve_conversation_and_profile_mode() -> None:
    profile_mode = ProfileMode.explicit("code-review-security")
    session = _session(
        persistence_mode=PersistenceMode.PERSISTENT,
        profile_mode=profile_mode,
    )
    _append_turn(session)

    original_turns = session.conversation.turns

    session.close(updated_at=_UPDATED_AT)
    session.mark_clean()

    later = datetime(
        2026,
        9,
        11,
        18,
        2,
        tzinfo=timezone.utc,
    )
    session.resume(updated_at=later)

    assert session.conversation.turns == original_turns
    assert session.profile_mode == profile_mode
    assert session.created_at == _CREATED_AT
    assert session.updated_at == later
    assert session.sync_state is SessionSyncState.DIRTY


def test_active_persistent_session_reset_marks_dirty() -> None:
    profile_mode = ProfileMode.explicit("code-review-security")
    session = _session(
        persistence_mode=PersistenceMode.PERSISTENT,
        authority=SessionAuthority.REMOTE,
        profile_mode=profile_mode,
    )
    _append_turn(session)

    session.reset_conversation(updated_at=_UPDATED_AT)

    assert session.conversation.turns == ()
    assert session.lifecycle is SessionLifecycle.ACTIVE
    assert session.session_id == "session-test"
    assert session.persistence_mode is PersistenceMode.PERSISTENT
    assert session.authority is SessionAuthority.REMOTE
    assert session.profile_mode == profile_mode
    assert session.created_at == _CREATED_AT
    assert session.updated_at == _UPDATED_AT
    assert session.sync_state is SessionSyncState.DIRTY


def test_active_ephemeral_session_reset_remains_clean() -> None:
    session = _session()
    _append_turn(session)

    session.reset_conversation(updated_at=_UPDATED_AT)

    assert session.conversation.turns == ()
    assert session.updated_at == _UPDATED_AT
    assert session.sync_state is SessionSyncState.CLEAN


@pytest.mark.parametrize(
    "lifecycle",
    [
        SessionLifecycle.CLOSED,
        SessionLifecycle.DELETED,
    ],
)
def test_non_active_session_cannot_reset_conversation(
    lifecycle: SessionLifecycle,
) -> None:
    session = _session(
        lifecycle=lifecycle,
        persistence_mode=PersistenceMode.PERSISTENT,
    )
    _append_turn(session)

    original_turns = session.conversation.turns
    original_updated_at = session.updated_at

    with pytest.raises(SessionLifecycleError):
        session.reset_conversation(updated_at=_UPDATED_AT)

    assert session.lifecycle is lifecycle
    assert session.conversation.turns == original_turns
    assert session.updated_at == original_updated_at
    assert session.sync_state is SessionSyncState.CLEAN


def test_reset_empty_active_conversation_is_valid_change() -> None:
    session = _session(
        persistence_mode=PersistenceMode.PERSISTENT,
    )

    session.reset_conversation(updated_at=_UPDATED_AT)

    assert session.conversation.turns == ()
    assert session.lifecycle is SessionLifecycle.ACTIVE
    assert session.updated_at == _UPDATED_AT
    assert session.sync_state is SessionSyncState.DIRTY


def test_mark_clean_clears_dirty_persistent_session() -> None:
    session = _session(
        persistence_mode=PersistenceMode.PERSISTENT,
    )

    session.close(updated_at=_UPDATED_AT)

    assert session.sync_state is SessionSyncState.DIRTY

    session.mark_clean()

    assert session.sync_state is SessionSyncState.CLEAN


def test_mark_clean_does_not_change_ephemeral_session() -> None:
    session = _session()

    session.mark_clean()

    assert session.sync_state is SessionSyncState.CLEAN


def test_ephemeral_commit_turn_updates_history_and_timestamp() -> None:
    session = _session(
        persistence_mode=PersistenceMode.EPHEMERAL,
    )

    updated_at = datetime(
        2026,
        9,
        11,
        20,
        0,
        tzinfo=timezone.utc,
    )

    turn = Turn(
        user=Message(
            role=MessageRole.USER,
            content="nova pergunta",
        ),
        assistant=Message(
            role=MessageRole.ASSISTANT,
            content="nova resposta",
        ),
    )

    session.commit_turn(
        turn,
        updated_at=updated_at,
    )

    assert session.conversation.turns == (turn,)
    assert session.updated_at == updated_at
    assert session.sync_state is SessionSyncState.CLEAN


def test_persistent_commit_turn_marks_session_dirty() -> None:
    session = _session(
        persistence_mode=PersistenceMode.PERSISTENT,
    )

    updated_at = datetime(
        2026,
        9,
        11,
        20,
        1,
        tzinfo=timezone.utc,
    )

    turn = Turn(
        user=Message(
            role=MessageRole.USER,
            content="pergunta",
        ),
        assistant=Message(
            role=MessageRole.ASSISTANT,
            content="resposta",
        ),
    )

    session.commit_turn(
        turn,
        updated_at=updated_at,
    )

    assert session.conversation.turns == (turn,)
    assert session.updated_at == updated_at
    assert session.sync_state is SessionSyncState.DIRTY


@pytest.mark.parametrize(
    "lifecycle",
    [
        SessionLifecycle.CLOSED,
        SessionLifecycle.DELETED,
    ],
)
def test_non_active_session_cannot_commit_turn(
    lifecycle: SessionLifecycle,
) -> None:
    session = _session()
    session.lifecycle = lifecycle

    original_updated_at = session.updated_at

    turn = Turn(
        user=Message(
            role=MessageRole.USER,
            content="pergunta",
        ),
        assistant=Message(
            role=MessageRole.ASSISTANT,
            content="resposta",
        ),
    )

    with pytest.raises(
        SessionLifecycleError,
        match="ACTIVE",
    ):
        session.commit_turn(
            turn,
            updated_at=datetime(
                2026,
                9,
                11,
                20,
                2,
                tzinfo=timezone.utc,
            ),
        )

    assert session.conversation.turns == ()
    assert session.updated_at == original_updated_at


def test_ephemeral_profile_mode_change_preserves_clean_state() -> None:
    session = _session(
        persistence_mode=PersistenceMode.EPHEMERAL,
    )

    updated_at = datetime(
        2026,
        9,
        11,
        20,
        3,
        tzinfo=timezone.utc,
    )

    profile_mode = ProfileMode.explicit(
        "code-review-security"
    )

    session.change_profile_mode(
        profile_mode,
        updated_at=updated_at,
    )

    assert session.profile_mode == profile_mode
    assert session.updated_at == updated_at
    assert session.sync_state is SessionSyncState.CLEAN


def test_persistent_profile_mode_change_marks_session_dirty() -> None:
    session = _session(
        persistence_mode=PersistenceMode.PERSISTENT,
    )

    updated_at = datetime(
        2026,
        9,
        11,
        20,
        4,
        tzinfo=timezone.utc,
    )

    profile_mode = ProfileMode.explicit(
        "code-review-security"
    )

    session.change_profile_mode(
        profile_mode,
        updated_at=updated_at,
    )

    assert session.profile_mode == profile_mode
    assert session.updated_at == updated_at
    assert session.sync_state is SessionSyncState.DIRTY


@pytest.mark.parametrize(
    "lifecycle",
    [
        SessionLifecycle.CLOSED,
        SessionLifecycle.DELETED,
    ],
)
def test_non_active_session_cannot_change_profile_mode(
    lifecycle: SessionLifecycle,
) -> None:
    session = _session()
    session.lifecycle = lifecycle

    original_profile_mode = session.profile_mode
    original_updated_at = session.updated_at

    with pytest.raises(
        SessionLifecycleError,
        match="ACTIVE",
    ):
        session.change_profile_mode(
            ProfileMode.explicit(
                "code-review-security"
            ),
            updated_at=datetime(
                2026,
                9,
                11,
                20,
                5,
                tzinfo=timezone.utc,
            ),
        )

    assert session.profile_mode == original_profile_mode
    assert session.updated_at == original_updated_at


def test_conversation_request_preserves_components() -> None:
    current_message = Message(
        role=MessageRole.USER,
        content="nova pergunta",
    )
    effective_context = EffectiveInferenceContext(
        turns=(),
        omitted_turn_count=2,
    )
    profile_mode = ProfileMode.explicit(
        "code-review-security"
    )

    request = ConversationRequest(
        current_message=current_message,
        effective_context=effective_context,
        profile_mode=profile_mode,
    )

    assert request.current_message == current_message
    assert request.effective_context == effective_context
    assert request.profile_mode == profile_mode


def test_conversation_request_rejects_assistant_current_message() -> None:
    with pytest.raises(
        ValueError,
        match="role 'user'",
    ):
        ConversationRequest(
            current_message=Message(
                role=MessageRole.ASSISTANT,
                content="resposta",
            ),
            effective_context=EffectiveInferenceContext(
                turns=(),
            ),
            profile_mode=ProfileMode.auto(),
        )


def test_conversation_request_is_immutable() -> None:
    request = ConversationRequest(
        current_message=Message(
            role=MessageRole.USER,
            content="pergunta",
        ),
        effective_context=EffectiveInferenceContext(
            turns=(),
        ),
        profile_mode=ProfileMode.auto(),
    )

    with pytest.raises(AttributeError):
        request.profile_mode = (  # type: ignore[misc]
            ProfileMode.explicit("code-review-security")
        )


def test_conversation_request_from_session_preserves_turn_order() -> None:
    session = _session()

    first = Turn(
        user=Message(
            role=MessageRole.USER,
            content="primeira",
        ),
        assistant=Message(
            role=MessageRole.ASSISTANT,
            content="resposta 1",
        ),
    )
    second = Turn(
        user=Message(
            role=MessageRole.USER,
            content="segunda",
        ),
        assistant=Message(
            role=MessageRole.ASSISTANT,
            content="resposta 2",
        ),
    )

    session.conversation.append(first)
    session.conversation.append(second)

    request = ConversationRequest.from_session(
        session,
        current_message=Message(
            role=MessageRole.USER,
            content="terceira",
        ),
    )

    assert request.effective_context.turns == (
        first,
        second,
    )
    assert request.effective_context.omitted_turn_count == 0
    assert request.effective_context.is_truncated is False


def test_conversation_request_from_session_preserves_auto_profile() -> None:
    session = _session(
        profile_mode=ProfileMode.auto(),
    )

    request = ConversationRequest.from_session(
        session,
        current_message=Message(
            role=MessageRole.USER,
            content="pergunta",
        ),
    )

    assert request.profile_mode == ProfileMode.auto()


def test_conversation_request_from_session_preserves_explicit_profile() -> None:
    profile_mode = ProfileMode.explicit(
        "code-review-security"
    )
    session = _session(
        profile_mode=profile_mode,
    )

    request = ConversationRequest.from_session(
        session,
        current_message=Message(
            role=MessageRole.USER,
            content="pergunta",
        ),
    )

    assert request.profile_mode == profile_mode


def test_conversation_request_creation_does_not_mutate_session() -> None:
    profile_mode = ProfileMode.explicit(
        "code-review-security"
    )
    session = _session(
        persistence_mode=PersistenceMode.PERSISTENT,
        profile_mode=profile_mode,
    )
    _append_turn(session)

    original_turns = session.conversation.turns
    original_updated_at = session.updated_at
    original_lifecycle = session.lifecycle
    original_sync_state = session.sync_state

    ConversationRequest.from_session(
        session,
        current_message=Message(
            role=MessageRole.USER,
            content="nova pergunta",
        ),
    )

    assert session.conversation.turns == original_turns
    assert session.profile_mode == profile_mode
    assert session.updated_at == original_updated_at
    assert session.lifecycle is original_lifecycle
    assert session.sync_state is original_sync_state


def test_conversation_request_is_snapshot_of_session_state() -> None:
    session = _session(
        profile_mode=ProfileMode.auto(),
    )

    first = Turn(
        user=Message(
            role=MessageRole.USER,
            content="primeira",
        ),
        assistant=Message(
            role=MessageRole.ASSISTANT,
            content="resposta 1",
        ),
    )
    session.conversation.append(first)

    request = ConversationRequest.from_session(
        session,
        current_message=Message(
            role=MessageRole.USER,
            content="mensagem atual",
        ),
    )

    second = Turn(
        user=Message(
            role=MessageRole.USER,
            content="segunda",
        ),
        assistant=Message(
            role=MessageRole.ASSISTANT,
            content="resposta 2",
        ),
    )

    session.commit_turn(
        second,
        updated_at=_UPDATED_AT,
    )
    session.change_profile_mode(
        ProfileMode.explicit(
            "code-review-security"
        ),
        updated_at=_UPDATED_AT,
    )

    assert session.conversation.turns == (
        first,
        second,
    )
    assert session.profile_mode == ProfileMode.explicit(
        "code-review-security"
    )

    assert request.effective_context.turns == (first,)
    assert request.effective_context.omitted_turn_count == 0
    assert request.profile_mode == ProfileMode.auto()
    assert request.current_message.content == "mensagem atual"


def test_conversation_request_materializes_successful_turn() -> None:
    current_message = Message(
        role=MessageRole.USER,
        content="pergunta atual",
    )
    assistant_message = Message(
        role=MessageRole.ASSISTANT,
        content="resposta válida",
    )

    request = ConversationRequest(
        current_message=current_message,
        effective_context=EffectiveInferenceContext(
            turns=(),
        ),
        profile_mode=ProfileMode.auto(),
    )
    result = ConversationResult.success(
        assistant_message
    )

    turn = request.materialize_turn(result)

    assert turn == Turn(
        user=current_message,
        assistant=assistant_message,
    )


def test_conversation_request_materialized_turn_preserves_message_identity() -> None:
    current_message = Message(
        role=MessageRole.USER,
        content="pergunta",
    )
    assistant_message = Message(
        role=MessageRole.ASSISTANT,
        content="resposta",
    )

    request = ConversationRequest(
        current_message=current_message,
        effective_context=EffectiveInferenceContext(
            turns=(),
        ),
        profile_mode=ProfileMode.auto(),
    )

    turn = request.materialize_turn(
        ConversationResult.success(
            assistant_message
        )
    )

    assert turn is not None
    assert turn.user is current_message
    assert turn.assistant is assistant_message


def test_conversation_request_failure_does_not_materialize_turn() -> None:
    request = ConversationRequest(
        current_message=Message(
            role=MessageRole.USER,
            content="pergunta",
        ),
        effective_context=EffectiveInferenceContext(
            turns=(),
        ),
        profile_mode=ProfileMode.auto(),
    )

    turn = request.materialize_turn(
        ConversationResult.failure()
    )

    assert turn is None


def test_conversation_request_materialization_does_not_mutate_session() -> None:
    profile_mode = ProfileMode.explicit(
        "code-review-security"
    )
    session = _session(
        persistence_mode=PersistenceMode.PERSISTENT,
        profile_mode=profile_mode,
    )
    _append_turn(session)

    original_turns = session.conversation.turns
    original_updated_at = session.updated_at
    original_lifecycle = session.lifecycle
    original_sync_state = session.sync_state

    request = ConversationRequest.from_session(
        session,
        current_message=Message(
            role=MessageRole.USER,
            content="nova pergunta",
        ),
    )
    result = ConversationResult.success(
        Message(
            role=MessageRole.ASSISTANT,
            content="nova resposta",
        )
    )

    turn = request.materialize_turn(result)

    assert turn is not None

    assert session.conversation.turns == original_turns
    assert session.profile_mode == profile_mode
    assert session.updated_at == original_updated_at
    assert session.lifecycle is original_lifecycle
    assert session.sync_state is original_sync_state


def test_commit_conversation_result_confirms_successful_turn() -> None:
    session = _session()

    request = ConversationRequest.from_session(
        session,
        current_message=Message(
            role=MessageRole.USER,
            content="pergunta atual",
        ),
    )
    assistant_message = Message(
        role=MessageRole.ASSISTANT,
        content="resposta válida",
    )

    turn = commit_conversation_result(
        session,
        request,
        ConversationResult.success(
            assistant_message
        ),
        updated_at=_UPDATED_AT,
    )

    assert turn is not None
    assert turn == Turn(
        user=request.current_message,
        assistant=assistant_message,
    )
    assert session.conversation.turns == (
        turn,
    )
    assert session.updated_at == _UPDATED_AT


def test_commit_conversation_result_preserves_message_identity() -> None:
    session = _session()

    current_message = Message(
        role=MessageRole.USER,
        content="pergunta",
    )
    assistant_message = Message(
        role=MessageRole.ASSISTANT,
        content="resposta",
    )

    request = ConversationRequest.from_session(
        session,
        current_message=current_message,
    )

    turn = commit_conversation_result(
        session,
        request,
        ConversationResult.success(
            assistant_message
        ),
        updated_at=_UPDATED_AT,
    )

    assert turn is not None
    assert turn.user is current_message
    assert turn.assistant is assistant_message
    assert session.conversation.turns[-1] is turn


def test_commit_conversation_result_appends_after_existing_history() -> None:
    session = _session()

    first = Turn(
        user=Message(
            role=MessageRole.USER,
            content="primeira",
        ),
        assistant=Message(
            role=MessageRole.ASSISTANT,
            content="resposta 1",
        ),
    )
    session.conversation.append(first)

    request = ConversationRequest.from_session(
        session,
        current_message=Message(
            role=MessageRole.USER,
            content="segunda",
        ),
    )

    turn = commit_conversation_result(
        session,
        request,
        ConversationResult.success(
            Message(
                role=MessageRole.ASSISTANT,
                content="resposta 2",
            )
        ),
        updated_at=_UPDATED_AT,
    )

    assert turn is not None
    assert session.conversation.turns == (
        first,
        turn,
    )


def test_commit_conversation_result_failure_does_not_commit() -> None:
    session = _session()
    _append_turn(session)

    original_turns = session.conversation.turns
    original_updated_at = session.updated_at
    original_sync_state = session.sync_state

    request = ConversationRequest.from_session(
        session,
        current_message=Message(
            role=MessageRole.USER,
            content="nova pergunta",
        ),
    )

    turn = commit_conversation_result(
        session,
        request,
        ConversationResult.failure(),
        updated_at=_UPDATED_AT,
    )

    assert turn is None
    assert session.conversation.turns == original_turns
    assert session.updated_at == original_updated_at
    assert session.sync_state is original_sync_state


def test_commit_conversation_result_ephemeral_session_remains_clean() -> None:
    session = _session(
        persistence_mode=PersistenceMode.EPHEMERAL,
    )

    request = ConversationRequest.from_session(
        session,
        current_message=Message(
            role=MessageRole.USER,
            content="pergunta",
        ),
    )

    commit_conversation_result(
        session,
        request,
        ConversationResult.success(
            Message(
                role=MessageRole.ASSISTANT,
                content="resposta",
            )
        ),
        updated_at=_UPDATED_AT,
    )

    assert len(session.conversation.turns) == 1
    assert session.updated_at == _UPDATED_AT
    assert session.sync_state is SessionSyncState.CLEAN


def test_commit_conversation_result_persistent_session_becomes_dirty() -> None:
    session = _session(
        persistence_mode=PersistenceMode.PERSISTENT,
    )

    assert session.sync_state is SessionSyncState.CLEAN

    request = ConversationRequest.from_session(
        session,
        current_message=Message(
            role=MessageRole.USER,
            content="pergunta",
        ),
    )

    commit_conversation_result(
        session,
        request,
        ConversationResult.success(
            Message(
                role=MessageRole.ASSISTANT,
                content="resposta",
            )
        ),
        updated_at=_UPDATED_AT,
    )

    assert len(session.conversation.turns) == 1
    assert session.updated_at == _UPDATED_AT
    assert session.sync_state is SessionSyncState.DIRTY


@pytest.mark.parametrize(
    "lifecycle",
    [
        SessionLifecycle.CLOSED,
        SessionLifecycle.DELETED,
    ],
)
def test_commit_conversation_result_rejects_non_active_session(
    lifecycle: SessionLifecycle,
) -> None:
    session = _session()
    session.lifecycle = lifecycle

    request = ConversationRequest.from_session(
        session,
        current_message=Message(
            role=MessageRole.USER,
            content="pergunta",
        ),
    )

    original_turns = session.conversation.turns
    original_updated_at = session.updated_at
    original_sync_state = session.sync_state

    with pytest.raises(
        SessionLifecycleError,
        match="ACTIVE",
    ):
        commit_conversation_result(
            session,
            request,
            ConversationResult.success(
                Message(
                    role=MessageRole.ASSISTANT,
                    content="resposta",
                )
            ),
            updated_at=_UPDATED_AT,
        )

    assert session.conversation.turns == original_turns
    assert session.updated_at == original_updated_at
    assert session.sync_state is original_sync_state


def test_commit_conversation_result_does_not_replace_logical_history_with_effective_context() -> None:
    session = _session()

    first = Turn(
        user=Message(
            role=MessageRole.USER,
            content="primeira",
        ),
        assistant=Message(
            role=MessageRole.ASSISTANT,
            content="resposta 1",
        ),
    )
    second = Turn(
        user=Message(
            role=MessageRole.USER,
            content="segunda",
        ),
        assistant=Message(
            role=MessageRole.ASSISTANT,
            content="resposta 2",
        ),
    )

    session.conversation.append(first)
    session.conversation.append(second)

    request = ConversationRequest(
        current_message=Message(
            role=MessageRole.USER,
            content="terceira",
        ),
        effective_context=EffectiveInferenceContext(
            turns=(second,),
            omitted_turn_count=1,
        ),
        profile_mode=session.profile_mode,
    )

    turn = commit_conversation_result(
        session,
        request,
        ConversationResult.success(
            Message(
                role=MessageRole.ASSISTANT,
                content="resposta 3",
            )
        ),
        updated_at=_UPDATED_AT,
    )

    assert turn is not None
    assert session.conversation.turns == (
        first,
        second,
        turn,
    )
