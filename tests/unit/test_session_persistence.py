from datetime import datetime, timezone
from typing import Any

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
    Session,
    SessionAuthority,
    SessionLifecycle,
    SessionSyncState,
    SessionLifecycleError,
)
from villaz_cli.session_persistence import (
    SessionIdentityMismatchError,
    SessionNotFoundError,
    SessionNotPersistentError,
    SessionPromotionError,
    SessionStateStore,
    SessionStorageError,
    SessionDeletedError,
    SessionHandle,
    resume_session,
    list_persisted_session_ids,
    load_session,
    persist_session,
    promote_to_persistent,
    purge_persisted_session,
    change_profile_mode_with_autosave,
    commit_turn_with_autosave,
    commit_conversation_result_with_autosave,
    close_session_with_autosave,
    delete_session_with_autosave,
    reset_conversation_with_autosave,
    shutdown_persistent_session,
)
from villaz_cli.session_state import (
    SESSION_SCHEMA_VERSION,
    UnsupportedSessionSchemaError,
    session_from_state,
    session_to_state,
)
from villaz_cli.session_lock import (
    SessionInUseError,
    SessionLockOwnershipError,
    SessionLockStore,
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
    19,
    0,
    tzinfo=timezone.utc,
)


class FakeSessionStateStore:
    def __init__(self) -> None:
        self.states: dict[str, dict[str, Any]] = {}
        self.fail_save = False
        self.fail_load = False
        self.fail_purge = False

    def save(
        self,
        *,
        session_id: str,
        state: dict[str, Any],
    ) -> None:
        if self.fail_save:
            raise SessionStorageError(
                "Falha simulada ao salvar Session."
            )

        self.states[session_id] = state

    def load(
        self,
        *,
        session_id: str,
    ) -> dict[str, Any]:
        if self.fail_load:
            raise SessionStorageError(
                "Falha simulada ao carregar Session."
            )

        try:
            return self.states[session_id]
        except KeyError as exc:
            raise SessionNotFoundError(
                f"Session não encontrada: {session_id}."
            ) from exc

    def list_session_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self.states))

    def purge(
        self,
        *,
        session_id: str,
    ) -> None:
        if self.fail_purge:
            raise SessionStorageError(
                "Falha simulada ao remover estado persistido."
            )

        try:
            del self.states[session_id]
        except KeyError as exc:
            raise SessionNotFoundError(
                f"Session não encontrada: {session_id}."
            ) from exc

class FakeSessionLockStore:
    def __init__(self) -> None:
        self.owners: dict[str, str] = {}
        self.fail_release = False

    def acquire(
        self,
        *,
        session_id: str,
        owner_id: str,
        pid: int,
    ) -> None:
        del pid

        current_owner = self.owners.get(
            session_id
        )

        if (
            current_owner is not None
            and current_owner != owner_id
        ):
            raise SessionInUseError(
                "A Session já está em uso por outro owner."
            )

        self.owners[session_id] = owner_id

    def release(
        self,
        *,
        session_id: str,
        owner_id: str,
    ) -> None:
        if self.fail_release:
            raise SessionLockOwnershipError(
                "falha simulada na liberação"
            )

        current_owner = self.owners.get(
            session_id
        )

        if current_owner is None:
            return

        if current_owner != owner_id:
            raise SessionLockOwnershipError(
                "O lock pertence a outro owner."
            )

        del self.owners[session_id]


def _persistent_session(
    *,
    session_id: str = "session-test",
    sync_state: SessionSyncState = SessionSyncState.DIRTY,
) -> Session:
    history = LogicalConversationHistory()

    history.append(
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

    return Session(
        session_id=session_id,
        conversation=history,
        persistence_mode=PersistenceMode.PERSISTENT,
        authority=SessionAuthority.LOCAL,
        profile_mode=ProfileMode.auto(),
        created_at=_CREATED_AT,
        updated_at=_UPDATED_AT,
        lifecycle=SessionLifecycle.ACTIVE,
        sync_state=sync_state,
    )


def _ephemeral_session() -> Session:
    return Session(
        session_id="ephemeral-session",
        conversation=LogicalConversationHistory(),
        persistence_mode=PersistenceMode.EPHEMERAL,
        authority=SessionAuthority.LOCAL,
        profile_mode=ProfileMode.auto(),
        created_at=_CREATED_AT,
        updated_at=_UPDATED_AT,
    )


def test_fake_store_satisfies_persistence_port() -> None:
    store: SessionStateStore = FakeSessionStateStore()

    assert store.list_session_ids() == ()


def test_successful_persist_marks_dirty_session_clean() -> None:
    store = FakeSessionStateStore()
    session = _persistent_session()

    assert session.sync_state is SessionSyncState.DIRTY

    persist_session(
        session,
        store=store,
    )

    assert session.sync_state is SessionSyncState.CLEAN
    assert session.session_id in store.states


def test_successful_persist_writes_serializable_state() -> None:
    store = FakeSessionStateStore()
    session = _persistent_session()

    persist_session(
        session,
        store=store,
    )

    state = store.states["session-test"]

    assert state["schema_version"] == SESSION_SCHEMA_VERSION
    assert state["session_id"] == "session-test"
    assert state["conversation"]["turns"] == [
        {
            "user": {
                "role": "user",
                "content": "mensagem",
            },
            "assistant": {
                "role": "assistant",
                "content": "resposta",
            },
        }
    ]


def test_persist_clean_session_remains_clean() -> None:
    store = FakeSessionStateStore()
    session = _persistent_session(
        sync_state=SessionSyncState.CLEAN,
    )

    persist_session(
        session,
        store=store,
    )

    assert session.sync_state is SessionSyncState.CLEAN


def test_save_failure_preserves_dirty_session() -> None:
    store = FakeSessionStateStore()
    store.fail_save = True

    session = _persistent_session()

    with pytest.raises(
        SessionStorageError,
        match="salvar",
    ):
        persist_session(
            session,
            store=store,
        )

    assert session.sync_state is SessionSyncState.DIRTY
    assert "session-test" not in store.states


def test_ephemeral_session_cannot_be_persisted() -> None:
    store = FakeSessionStateStore()
    session = _ephemeral_session()

    with pytest.raises(
        SessionNotPersistentError,
        match="EPHEMERAL",
    ):
        persist_session(
            session,
            store=store,
        )

    assert store.states == {}


def test_load_reconstructs_clean_session() -> None:
    store = FakeSessionStateStore()
    original = _persistent_session()

    store.states[original.session_id] = session_to_state(
        original
    )

    restored = load_session(
        original.session_id,
        store=store,
    )

    assert restored.session_id == original.session_id
    assert restored.conversation.turns == original.conversation.turns
    assert restored.profile_mode == original.profile_mode
    assert restored.lifecycle is original.lifecycle
    assert restored.sync_state is SessionSyncState.CLEAN


def test_load_does_not_mutate_stored_state() -> None:
    store = FakeSessionStateStore()
    original = _persistent_session()

    state = session_to_state(original)
    store.states[original.session_id] = state

    load_session(
        original.session_id,
        store=store,
    )

    assert store.states[original.session_id] is state


def test_load_missing_session_is_explicit_error() -> None:
    store = FakeSessionStateStore()

    with pytest.raises(
        SessionNotFoundError,
        match="não encontrada",
    ):
        load_session(
            "missing-session",
            store=store,
        )


def test_load_storage_failure_is_explicit_error() -> None:
    store = FakeSessionStateStore()
    store.fail_load = True

    with pytest.raises(
        SessionStorageError,
        match="carregar",
    ):
        load_session(
            "session-test",
            store=store,
        )


def test_load_rejects_unsupported_schema_without_fallback() -> None:
    store = FakeSessionStateStore()
    original = _persistent_session()

    state = session_to_state(original)
    state["schema_version"] = 999
    store.states[original.session_id] = state

    with pytest.raises(
        UnsupportedSessionSchemaError,
        match="não suportado",
    ):
        load_session(
            original.session_id,
            store=store,
        )


def test_load_rejects_session_identity_mismatch() -> None:
    store = FakeSessionStateStore()

    stored = _persistent_session(
        session_id="different-session",
    )

    store.states["requested-session"] = session_to_state(
        stored
    )

    with pytest.raises(
        SessionIdentityMismatchError,
        match="identidade",
    ):
        load_session(
            "requested-session",
            store=store,
        )


def test_list_returns_only_session_ids() -> None:
    store = FakeSessionStateStore()

    store.states["session-b"] = session_to_state(
        _persistent_session(
            session_id="session-b",
        )
    )
    store.states["session-a"] = session_to_state(
        _persistent_session(
            session_id="session-a",
        )
    )

    assert list_persisted_session_ids(
        store=store,
    ) == (
        "session-a",
        "session-b",
    )


def test_purge_removes_only_persisted_record() -> None:
    store = FakeSessionStateStore()
    session = _persistent_session()

    store.states[session.session_id] = session_to_state(
        session
    )

    purge_persisted_session(
        session.session_id,
        store=store,
    )

    assert store.states == {}

    assert session.lifecycle is SessionLifecycle.ACTIVE
    assert session.session_id == "session-test"


def test_purge_does_not_change_logical_deleted_state() -> None:
    store = FakeSessionStateStore()
    session = _persistent_session()

    session.delete(
        updated_at=_UPDATED_AT,
    )

    store.states[session.session_id] = session_to_state(
        session
    )

    purge_persisted_session(
        session.session_id,
        store=store,
    )

    assert store.states == {}
    assert session.lifecycle is SessionLifecycle.DELETED


def test_purge_missing_session_is_explicit_error() -> None:
    store = FakeSessionStateStore()

    with pytest.raises(SessionNotFoundError):
        purge_persisted_session(
            "missing-session",
            store=store,
        )


def test_purge_storage_failure_is_explicit_error() -> None:
    store = FakeSessionStateStore()
    store.fail_purge = True

    with pytest.raises(
        SessionStorageError,
        match="remover",
    ):
        purge_persisted_session(
            "session-test",
            store=store,
        )


def test_active_ephemeral_session_can_be_promoted() -> None:
    store = FakeSessionStateStore()
    session = _ephemeral_session()

    promote_to_persistent(
        session,
        store=store,
    )

    assert session.persistence_mode is PersistenceMode.PERSISTENT
    assert session.sync_state is SessionSyncState.CLEAN
    assert session.lifecycle is SessionLifecycle.ACTIVE
    assert session.session_id == "ephemeral-session"


def test_promotion_persists_persistent_candidate_state() -> None:
    store = FakeSessionStateStore()
    session = _ephemeral_session()

    promote_to_persistent(
        session,
        store=store,
    )

    state = store.states["ephemeral-session"]

    assert state["session_id"] == "ephemeral-session"
    assert state["persistence_mode"] == "persistent"
    assert state["lifecycle"] == "active"
    assert state["authority"] == "local"
    assert state["profile_mode"] == {
        "kind": "auto",
        "profile_id": None,
    }
    assert state["created_at"] == _CREATED_AT.isoformat()
    assert state["updated_at"] == _UPDATED_AT.isoformat()


def test_promotion_preserves_session_semantic_state() -> None:
    store = FakeSessionStateStore()
    session = _ephemeral_session()

    session.conversation.append(
        Turn(
            user=Message(
                role=MessageRole.USER,
                content="mensagem anterior",
            ),
            assistant=Message(
                role=MessageRole.ASSISTANT,
                content="resposta anterior",
            ),
        )
    )

    original_conversation = session.conversation
    original_turns = session.conversation.turns
    original_profile_mode = session.profile_mode
    original_created_at = session.created_at
    original_updated_at = session.updated_at
    original_authority = session.authority

    promote_to_persistent(
        session,
        store=store,
    )

    assert session.conversation is original_conversation
    assert session.conversation.turns == original_turns
    assert session.profile_mode == original_profile_mode
    assert session.created_at == original_created_at
    assert session.updated_at == original_updated_at
    assert session.authority is original_authority
    assert session.lifecycle is SessionLifecycle.ACTIVE


def test_promotion_failure_preserves_ephemeral_session() -> None:
    store = FakeSessionStateStore()
    store.fail_save = True

    session = _ephemeral_session()

    original_conversation = session.conversation
    original_profile_mode = session.profile_mode
    original_created_at = session.created_at
    original_updated_at = session.updated_at
    original_authority = session.authority
    original_lifecycle = session.lifecycle

    with pytest.raises(
        SessionStorageError,
        match="salvar",
    ):
        promote_to_persistent(
            session,
            store=store,
        )

    assert session.persistence_mode is PersistenceMode.EPHEMERAL
    assert session.sync_state is SessionSyncState.CLEAN
    assert session.conversation is original_conversation
    assert session.profile_mode == original_profile_mode
    assert session.created_at == original_created_at
    assert session.updated_at == original_updated_at
    assert session.authority is original_authority
    assert session.lifecycle is original_lifecycle
    assert "ephemeral-session" not in store.states


def test_persistent_session_cannot_be_promoted_again() -> None:
    store = FakeSessionStateStore()
    session = _persistent_session(
        sync_state=SessionSyncState.CLEAN,
    )

    with pytest.raises(
        SessionPromotionError,
        match="EPHEMERAL",
    ):
        promote_to_persistent(
            session,
            store=store,
        )

    assert store.states == {}


@pytest.mark.parametrize(
    "lifecycle",
    [
        SessionLifecycle.CLOSED,
        SessionLifecycle.DELETED,
    ],
)
def test_non_active_ephemeral_session_cannot_be_promoted(
    lifecycle: SessionLifecycle,
) -> None:
    store = FakeSessionStateStore()

    session = _ephemeral_session()
    session.lifecycle = lifecycle

    with pytest.raises(
        SessionPromotionError,
        match="ACTIVE",
    ):
        promote_to_persistent(
            session,
            store=store,
        )

    assert session.persistence_mode is PersistenceMode.EPHEMERAL
    assert session.lifecycle is lifecycle
    assert store.states == {}


def test_ephemeral_commit_turn_does_not_touch_store() -> None:
    store = FakeSessionStateStore()
    store.fail_save = True

    session = _ephemeral_session()

    updated_at = datetime(
        2026,
        9,
        11,
        20,
        10,
        tzinfo=timezone.utc,
    )

    turn = Turn(
        user=Message(
            role=MessageRole.USER,
            content="pergunta efêmera",
        ),
        assistant=Message(
            role=MessageRole.ASSISTANT,
            content="resposta efêmera",
        ),
    )

    commit_turn_with_autosave(
        session,
        turn,
        updated_at=updated_at,
        store=store,
    )

    assert session.conversation.turns == (turn,)
    assert session.updated_at == updated_at
    assert session.sync_state is SessionSyncState.CLEAN
    assert store.states == {}


def test_ephemeral_conversation_result_commit_does_not_touch_store() -> None:
    store = FakeSessionStateStore()
    session = _ephemeral_session()

    current_message = Message(
        role=MessageRole.USER,
        content="pergunta atual",
    )
    assistant_message = Message(
        role=MessageRole.ASSISTANT,
        content="resposta atual",
    )

    request = ConversationRequest.from_session(
        session,
        current_message=current_message,
    )

    turn = commit_conversation_result_with_autosave(
        session,
        request,
        ConversationResult.success(
            assistant_message
        ),
        updated_at=_UPDATED_AT,
        store=store,
    )

    assert turn is not None
    assert turn.user is current_message
    assert turn.assistant is assistant_message
    assert session.conversation.turns == (
        turn,
    )
    assert session.sync_state is SessionSyncState.CLEAN
    assert store.states == {}


def test_persistent_conversation_result_autosaves_and_returns_clean() -> None:
    store = FakeSessionStateStore()
    session = _persistent_session(
        sync_state=SessionSyncState.CLEAN,
    )

    original_count = len(
        session.conversation.turns
    )

    current_message = Message(
        role=MessageRole.USER,
        content="nova pergunta",
    )
    assistant_message = Message(
        role=MessageRole.ASSISTANT,
        content="nova resposta",
    )

    request = ConversationRequest.from_session(
        session,
        current_message=current_message,
    )

    turn = commit_conversation_result_with_autosave(
        session,
        request,
        ConversationResult.success(
            assistant_message
        ),
        updated_at=_UPDATED_AT,
        store=store,
    )

    assert turn is not None
    assert len(session.conversation.turns) == (
        original_count + 1
    )
    assert session.conversation.turns[-1] is turn
    assert session.sync_state is SessionSyncState.CLEAN

    state = store.states[
        session.session_id
    ]

    assert len(
        state["conversation"]["turns"]
    ) == original_count + 1

    assert (
        state["conversation"]["turns"][-1]
        ["user"]["content"]
        == "nova pergunta"
    )
    assert (
        state["conversation"]["turns"][-1]
        ["assistant"]["content"]
        == "nova resposta"
    )


def test_failed_conversation_result_does_not_commit_or_save() -> None:
    store = FakeSessionStateStore()
    session = _persistent_session(
        sync_state=SessionSyncState.CLEAN,
    )

    original_turns = (
        session.conversation.turns
    )
    original_updated_at = (
        session.updated_at
    )
    original_sync_state = (
        session.sync_state
    )

    request = ConversationRequest.from_session(
        session,
        current_message=Message(
            role=MessageRole.USER,
            content="mensagem não confirmada",
        ),
    )

    turn = commit_conversation_result_with_autosave(
        session,
        request,
        ConversationResult.failure(),
        updated_at=_UPDATED_AT,
        store=store,
    )

    assert turn is None
    assert session.conversation.turns == original_turns
    assert session.updated_at == original_updated_at
    assert session.sync_state is original_sync_state
    assert store.states == {}


def test_conversation_result_autosave_failure_preserves_memory_and_dirty_state() -> None:
    store = FakeSessionStateStore()
    store.fail_save = True

    session = _persistent_session(
        sync_state=SessionSyncState.CLEAN,
    )

    original_count = len(
        session.conversation.turns
    )

    request = ConversationRequest.from_session(
        session,
        current_message=Message(
            role=MessageRole.USER,
            content="pergunta nova",
        ),
    )

    with pytest.raises(
        SessionStorageError,
        match="salvar",
    ):
        commit_conversation_result_with_autosave(
            session,
            request,
            ConversationResult.success(
                Message(
                    role=MessageRole.ASSISTANT,
                    content="resposta nova",
                )
            ),
            updated_at=_UPDATED_AT,
            store=store,
        )

    assert len(session.conversation.turns) == (
        original_count + 1
    )
    assert (
        session.conversation.turns[-1]
        .user.content
        == "pergunta nova"
    )
    assert (
        session.conversation.turns[-1]
        .assistant.content
        == "resposta nova"
    )
    assert session.sync_state is SessionSyncState.DIRTY
    assert store.states == {}


def test_conversation_result_autosave_persists_full_logical_history_not_effective_context() -> None:
    store = FakeSessionStateStore()
    session = _persistent_session(
        sync_state=SessionSyncState.CLEAN,
    )

    first = session.conversation.turns[0]

    second = Turn(
        user=Message(
            role=MessageRole.USER,
            content="segunda pergunta",
        ),
        assistant=Message(
            role=MessageRole.ASSISTANT,
            content="segunda resposta",
        ),
    )
    session.conversation.append(
        second
    )

    request = ConversationRequest(
        current_message=Message(
            role=MessageRole.USER,
            content="terceira pergunta",
        ),
        effective_context=(
            EffectiveInferenceContext(
                turns=(second,),
                omitted_turn_count=1,
            )
        ),
        profile_mode=session.profile_mode,
    )

    turn = commit_conversation_result_with_autosave(
        session,
        request,
        ConversationResult.success(
            Message(
                role=MessageRole.ASSISTANT,
                content="terceira resposta",
            )
        ),
        updated_at=_UPDATED_AT,
        store=store,
    )

    assert turn is not None

    assert session.conversation.turns == (
        first,
        second,
        turn,
    )

    state = store.states[
        session.session_id
    ]

    persisted_turns = (
        state["conversation"]["turns"]
    )

    assert len(persisted_turns) == 3
    assert (
        persisted_turns[0]["user"]["content"]
        == first.user.content
    )
    assert (
        persisted_turns[1]["user"]["content"]
        == "segunda pergunta"
    )
    assert (
        persisted_turns[2]["user"]["content"]
        == "terceira pergunta"
    )


@pytest.mark.parametrize(
    "lifecycle",
    [
        SessionLifecycle.CLOSED,
        SessionLifecycle.DELETED,
    ],
)
def test_conversation_result_autosave_rejects_non_active_session_without_save(
    lifecycle: SessionLifecycle,
) -> None:
    store = FakeSessionStateStore()
    session = _persistent_session(
        sync_state=SessionSyncState.CLEAN,
    )
    session.lifecycle = lifecycle

    original_turns = (
        session.conversation.turns
    )
    original_updated_at = (
        session.updated_at
    )
    original_sync_state = (
        session.sync_state
    )

    request = ConversationRequest.from_session(
        session,
        current_message=Message(
            role=MessageRole.USER,
            content="pergunta",
        ),
    )

    with pytest.raises(
        SessionLifecycleError,
        match="ACTIVE",
    ):
        commit_conversation_result_with_autosave(
            session,
            request,
            ConversationResult.success(
                Message(
                    role=MessageRole.ASSISTANT,
                    content="resposta",
                )
            ),
            updated_at=_UPDATED_AT,
            store=store,
        )

    assert session.conversation.turns == original_turns
    assert session.updated_at == original_updated_at
    assert session.sync_state is original_sync_state
    assert store.states == {}


def test_persistent_commit_turn_autosaves_and_returns_clean() -> None:
    store = FakeSessionStateStore()

    session = _persistent_session(
        sync_state=SessionSyncState.CLEAN,
    )

    updated_at = datetime(
        2026,
        9,
        11,
        20,
        11,
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

    commit_turn_with_autosave(
        session,
        turn,
        updated_at=updated_at,
        store=store,
    )

    assert session.sync_state is SessionSyncState.CLEAN
    assert session.updated_at == updated_at
    assert session.conversation.turns[-1] == turn

    state = store.states["session-test"]

    assert state["updated_at"] == updated_at.isoformat()
    assert state["conversation"]["turns"][-1] == {
        "user": {
            "role": "user",
            "content": "nova pergunta",
        },
        "assistant": {
            "role": "assistant",
            "content": "nova resposta",
        },
    }


def test_commit_turn_autosave_failure_preserves_memory_and_dirty_state() -> None:
    store = FakeSessionStateStore()
    store.fail_save = True

    session = _persistent_session(
        sync_state=SessionSyncState.CLEAN,
    )

    original_count = len(
        session.conversation.turns
    )

    updated_at = datetime(
        2026,
        9,
        11,
        20,
        12,
        tzinfo=timezone.utc,
    )

    turn = Turn(
        user=Message(
            role=MessageRole.USER,
            content="não desfazer",
        ),
        assistant=Message(
            role=MessageRole.ASSISTANT,
            content="permanece em memória",
        ),
    )

    with pytest.raises(
        SessionStorageError,
        match="salvar",
    ):
        commit_turn_with_autosave(
            session,
            turn,
            updated_at=updated_at,
            store=store,
        )

    assert len(session.conversation.turns) == original_count + 1
    assert session.conversation.turns[-1] == turn
    assert session.updated_at == updated_at
    assert session.sync_state is SessionSyncState.DIRTY


def test_ephemeral_profile_change_does_not_touch_store() -> None:
    store = FakeSessionStateStore()
    store.fail_save = True

    session = _ephemeral_session()

    updated_at = datetime(
        2026,
        9,
        11,
        20,
        13,
        tzinfo=timezone.utc,
    )

    profile_mode = ProfileMode.explicit(
        "code-review-security"
    )

    change_profile_mode_with_autosave(
        session,
        profile_mode,
        updated_at=updated_at,
        store=store,
    )

    assert session.profile_mode == profile_mode
    assert session.updated_at == updated_at
    assert session.sync_state is SessionSyncState.CLEAN
    assert store.states == {}


def test_persistent_profile_change_autosaves_and_returns_clean() -> None:
    store = FakeSessionStateStore()

    session = _persistent_session(
        sync_state=SessionSyncState.CLEAN,
    )

    updated_at = datetime(
        2026,
        9,
        11,
        20,
        14,
        tzinfo=timezone.utc,
    )

    profile_mode = ProfileMode.explicit(
        "code-review-security"
    )

    change_profile_mode_with_autosave(
        session,
        profile_mode,
        updated_at=updated_at,
        store=store,
    )

    assert session.profile_mode == profile_mode
    assert session.updated_at == updated_at
    assert session.sync_state is SessionSyncState.CLEAN

    state = store.states["session-test"]

    assert state["profile_mode"] == {
        "kind": "explicit",
        "profile_id": "code-review-security",
    }
    assert state["updated_at"] == updated_at.isoformat()


def test_profile_change_autosave_failure_preserves_memory_and_dirty_state() -> None:
    store = FakeSessionStateStore()
    store.fail_save = True

    session = _persistent_session(
        sync_state=SessionSyncState.CLEAN,
    )

    updated_at = datetime(
        2026,
        9,
        11,
        20,
        15,
        tzinfo=timezone.utc,
    )

    profile_mode = ProfileMode.explicit(
        "code-review-security"
    )

    with pytest.raises(
        SessionStorageError,
        match="salvar",
    ):
        change_profile_mode_with_autosave(
            session,
            profile_mode,
            updated_at=updated_at,
            store=store,
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
def test_commit_turn_autosave_rejects_non_active_session_without_store_write(
    lifecycle: SessionLifecycle,
) -> None:
    store = FakeSessionStateStore()

    session = _persistent_session(
        sync_state=SessionSyncState.CLEAN,
    )
    session.lifecycle = lifecycle

    original_turns = session.conversation.turns

    with pytest.raises(
        SessionLifecycleError,
        match="ACTIVE",
    ):
        commit_turn_with_autosave(
            session,
            Turn(
                user=Message(
                    role=MessageRole.USER,
                    content="inválida",
                ),
                assistant=Message(
                    role=MessageRole.ASSISTANT,
                    content="inválida",
                ),
            ),
            updated_at=_UPDATED_AT,
            store=store,
        )

    assert session.conversation.turns == original_turns
    assert session.sync_state is SessionSyncState.CLEAN
    assert store.states == {}


@pytest.mark.parametrize(
    "lifecycle",
    [
        SessionLifecycle.CLOSED,
        SessionLifecycle.DELETED,
    ],
)
def test_profile_change_autosave_rejects_non_active_session_without_store_write(
    lifecycle: SessionLifecycle,
) -> None:
    store = FakeSessionStateStore()

    session = _persistent_session(
        sync_state=SessionSyncState.CLEAN,
    )
    session.lifecycle = lifecycle

    original_profile_mode = session.profile_mode

    with pytest.raises(
        SessionLifecycleError,
        match="ACTIVE",
    ):
        change_profile_mode_with_autosave(
            session,
            ProfileMode.explicit(
                "code-review-security"
            ),
            updated_at=_UPDATED_AT,
            store=store,
        )

    assert session.profile_mode == original_profile_mode
    assert session.sync_state is SessionSyncState.CLEAN
    assert store.states == {}


def test_resume_closed_persistent_session_returns_locked_handle() -> None:
    store = FakeSessionStateStore()
    lock_store = FakeSessionLockStore()

    persisted = _persistent_session(
        sync_state=SessionSyncState.CLEAN,
    )
    persisted.lifecycle = SessionLifecycle.CLOSED

    store.states[persisted.session_id] = session_to_state(
        persisted
    )

    resumed_at = datetime(
        2026,
        9,
        12,
        0,
        10,
        tzinfo=timezone.utc,
    )

    handle = resume_session(
        persisted.session_id,
        owner_id="owner-a",
        updated_at=resumed_at,
        store=store,
        lock_store=lock_store,
    )

    assert isinstance(
        handle,
        SessionHandle,
    )
    assert handle.owner_id == "owner-a"
    assert handle.session.lifecycle is SessionLifecycle.ACTIVE
    assert handle.session.persistence_mode is PersistenceMode.PERSISTENT
    assert handle.session.sync_state is SessionSyncState.CLEAN
    assert handle.session.updated_at == resumed_at
    assert lock_store.owners == {
        persisted.session_id: "owner-a"
    }

    stored_state = store.states[
        persisted.session_id
    ]

    assert stored_state["lifecycle"] == "active"
    assert stored_state["updated_at"] == resumed_at.isoformat()


def test_resume_closed_session_preserves_semantic_state() -> None:
    store = FakeSessionStateStore()
    lock_store = FakeSessionLockStore()

    persisted = _persistent_session(
        sync_state=SessionSyncState.CLEAN,
    )
    persisted.lifecycle = SessionLifecycle.CLOSED
    persisted.profile_mode = ProfileMode.explicit(
        "code-review-security"
    )

    original_turns = persisted.conversation.turns

    store.states[persisted.session_id] = session_to_state(
        persisted
    )

    handle = resume_session(
        persisted.session_id,
        owner_id="owner-a",
        updated_at=datetime(
            2026,
            9,
            12,
            0,
            11,
            tzinfo=timezone.utc,
        ),
        store=store,
        lock_store=lock_store,
    )

    session = handle.session

    assert session.session_id == persisted.session_id
    assert session.created_at == persisted.created_at
    assert session.authority is persisted.authority
    assert session.profile_mode == persisted.profile_mode
    assert session.conversation.turns == original_turns


def test_resume_active_session_acquires_lock_without_rewrite() -> None:
    store = FakeSessionStateStore()
    lock_store = FakeSessionLockStore()

    persisted = _persistent_session(
        sync_state=SessionSyncState.CLEAN,
    )

    original_state = session_to_state(
        persisted
    )

    store.states[persisted.session_id] = original_state.copy()
    store.fail_save = True

    handle = resume_session(
        persisted.session_id,
        owner_id="owner-a",
        updated_at=datetime(
            2026,
            9,
            12,
            0,
            12,
            tzinfo=timezone.utc,
        ),
        store=store,
        lock_store=lock_store,
    )

    assert handle.session.lifecycle is SessionLifecycle.ACTIVE
    assert handle.session.sync_state is SessionSyncState.CLEAN
    assert handle.session.updated_at == persisted.updated_at
    assert store.states[persisted.session_id] == original_state
    assert lock_store.owners[persisted.session_id] == "owner-a"


def test_second_owner_cannot_resume_locked_session() -> None:
    store = FakeSessionStateStore()
    lock_store = FakeSessionLockStore()

    persisted = _persistent_session(
        sync_state=SessionSyncState.CLEAN,
    )

    store.states[persisted.session_id] = session_to_state(
        persisted
    )

    first_handle = resume_session(
        persisted.session_id,
        owner_id="owner-a",
        updated_at=_UPDATED_AT,
        store=store,
        lock_store=lock_store,
    )

    assert first_handle.owner_id == "owner-a"

    with pytest.raises(
        SessionInUseError,
    ):
        resume_session(
            persisted.session_id,
            owner_id="owner-b",
            updated_at=_UPDATED_AT,
            store=store,
            lock_store=lock_store,
        )

    assert lock_store.owners[persisted.session_id] == "owner-a"


def test_deleted_session_releases_lock_before_error() -> None:
    store = FakeSessionStateStore()
    lock_store = FakeSessionLockStore()

    persisted = _persistent_session(
        sync_state=SessionSyncState.CLEAN,
    )
    persisted.lifecycle = SessionLifecycle.DELETED

    store.states[persisted.session_id] = session_to_state(
        persisted
    )

    with pytest.raises(
        SessionDeletedError,
        match="DELETED",
    ):
        resume_session(
            persisted.session_id,
            owner_id="owner-a",
            updated_at=_UPDATED_AT,
            store=store,
            lock_store=lock_store,
        )

    assert lock_store.owners == {}


def test_resume_missing_session_releases_lock() -> None:
    store = FakeSessionStateStore()
    lock_store = FakeSessionLockStore()

    with pytest.raises(
        SessionNotFoundError,
    ):
        resume_session(
            "missing-session",
            owner_id="owner-a",
            updated_at=_UPDATED_AT,
            store=store,
            lock_store=lock_store,
        )

    assert lock_store.owners == {}


def test_resume_unsupported_schema_releases_lock() -> None:
    store = FakeSessionStateStore()
    lock_store = FakeSessionLockStore()

    session = _persistent_session(
        sync_state=SessionSyncState.CLEAN,
    )

    state = session_to_state(
        session
    )
    state["schema_version"] = (
        SESSION_SCHEMA_VERSION + 1
    )

    store.states[
        session.session_id
    ] = state

    with pytest.raises(
        UnsupportedSessionSchemaError,
    ):
        resume_session(
            session.session_id,
            owner_id="owner-a",
            updated_at=_UPDATED_AT,
            store=store,
            lock_store=lock_store,
        )

    assert lock_store.owners == {}


def test_resume_persist_failure_releases_lock_and_preserves_storage() -> None:
    store = FakeSessionStateStore()
    lock_store = FakeSessionLockStore()

    persisted = _persistent_session(
        sync_state=SessionSyncState.CLEAN,
    )
    persisted.lifecycle = SessionLifecycle.CLOSED

    original_state = session_to_state(
        persisted
    )

    store.states[
        persisted.session_id
    ] = original_state.copy()

    store.fail_save = True

    with pytest.raises(
        SessionStorageError,
        match="salvar",
    ):
        resume_session(
            persisted.session_id,
            owner_id="owner-a",
            updated_at=_UPDATED_AT,
            store=store,
            lock_store=lock_store,
        )

    assert store.states[
        persisted.session_id
    ] == original_state

    assert lock_store.owners == {}


def test_resume_cleanup_failure_does_not_replace_original_error() -> None:
    store = FakeSessionStateStore()
    lock_store = FakeSessionLockStore()

    lock_store.fail_release = True

    with pytest.raises(
        SessionNotFoundError,
    ) as exc_info:
        resume_session(
            "missing-session",
            owner_id="owner-a",
            updated_at=_UPDATED_AT,
            store=store,
            lock_store=lock_store,
        )

    assert any(
        "Falha adicional ao liberar o lock"
        in note
        for note in exc_info.value.__notes__
    )


def test_close_session_with_autosave_persists_and_releases_lock() -> None:
    store = FakeSessionStateStore()
    lock_store = FakeSessionLockStore()

    session = _persistent_session(
        sync_state=SessionSyncState.CLEAN,
    )

    handle = SessionHandle(
        session=session,
        owner_id="owner-a",
    )

    lock_store.owners[
        session.session_id
    ] = "owner-a"

    close_session_with_autosave(
        handle,
        updated_at=_UPDATED_AT,
        store=store,
        lock_store=lock_store,
    )

    assert session.lifecycle is SessionLifecycle.CLOSED
    assert session.updated_at == _UPDATED_AT
    assert session.sync_state is SessionSyncState.CLEAN

    assert store.states[
        session.session_id
    ]["lifecycle"] == "closed"

    assert lock_store.owners == {}


def test_close_session_persist_failure_keeps_dirty_memory_and_lock() -> None:
    store = FakeSessionStateStore()
    lock_store = FakeSessionLockStore()

    session = _persistent_session(
        sync_state=SessionSyncState.CLEAN,
    )

    handle = SessionHandle(
        session=session,
        owner_id="owner-a",
    )

    lock_store.owners[
        session.session_id
    ] = "owner-a"

    store.fail_save = True

    with pytest.raises(
        SessionStorageError,
        match="salvar",
    ):
        close_session_with_autosave(
            handle,
            updated_at=_UPDATED_AT,
            store=store,
            lock_store=lock_store,
        )

    assert session.lifecycle is SessionLifecycle.CLOSED
    assert session.updated_at == _UPDATED_AT
    assert session.sync_state is SessionSyncState.DIRTY

    assert lock_store.owners == {
        session.session_id: "owner-a"
    }


def test_close_session_release_failure_keeps_persisted_clean_state() -> None:
    store = FakeSessionStateStore()
    lock_store = FakeSessionLockStore()

    session = _persistent_session(
        sync_state=SessionSyncState.CLEAN,
    )

    handle = SessionHandle(
        session=session,
        owner_id="owner-a",
    )

    lock_store.owners[
        session.session_id
    ] = "owner-a"

    lock_store.fail_release = True

    with pytest.raises(
        SessionLockOwnershipError,
        match="falha simulada",
    ):
        close_session_with_autosave(
            handle,
            updated_at=_UPDATED_AT,
            store=store,
            lock_store=lock_store,
        )

    assert session.lifecycle is SessionLifecycle.CLOSED
    assert session.sync_state is SessionSyncState.CLEAN

    assert store.states[
        session.session_id
    ]["lifecycle"] == "closed"

    assert lock_store.owners == {
        session.session_id: "owner-a"
    }


@pytest.mark.parametrize(
    "lifecycle",
    [
        SessionLifecycle.CLOSED,
        SessionLifecycle.DELETED,
    ],
)
def test_close_session_invalid_lifecycle_does_not_acquire_lock_or_write(
    lifecycle: SessionLifecycle,
) -> None:
    store = FakeSessionStateStore()
    lock_store = FakeSessionLockStore()

    session = _persistent_session(
        sync_state=SessionSyncState.CLEAN,
    )
    session.lifecycle = lifecycle

    handle = SessionHandle(
        session=session,
        owner_id="owner-a",
    )

    original_updated_at = session.updated_at

    with pytest.raises(
        SessionLifecycleError,
        match="ACTIVE",
    ):
        close_session_with_autosave(
            handle,
            updated_at=_UPDATED_AT,
            store=store,
            lock_store=lock_store,
        )

    assert session.lifecycle is lifecycle
    assert session.updated_at == original_updated_at
    assert session.sync_state is SessionSyncState.CLEAN
    assert lock_store.owners == {}
    assert store.states == {}


def test_reset_conversation_with_autosave_persists_and_keeps_lock() -> None:
    store = FakeSessionStateStore()
    lock_store = FakeSessionLockStore()

    session = _persistent_session(
        sync_state=SessionSyncState.CLEAN,
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

    session.conversation.append(
        turn
    )

    handle = SessionHandle(
        session=session,
        owner_id="owner-a",
    )

    lock_store.owners[
        session.session_id
    ] = "owner-a"

    reset_conversation_with_autosave(
        handle,
        updated_at=_UPDATED_AT,
        store=store,
        lock_store=lock_store,
    )

    assert session.conversation.turns == ()
    assert session.lifecycle is SessionLifecycle.ACTIVE
    assert session.updated_at == _UPDATED_AT
    assert session.sync_state is SessionSyncState.CLEAN

    stored_state = store.states[
        session.session_id
    ]

    assert stored_state["conversation"]["turns"] == []

    assert lock_store.owners == {
        session.session_id: "owner-a"
    }


def test_reset_empty_conversation_is_persisted_as_explicit_change() -> None:
    store = FakeSessionStateStore()
    lock_store = FakeSessionLockStore()

    session = _persistent_session(
        sync_state=SessionSyncState.CLEAN,
    )

    handle = SessionHandle(
        session=session,
        owner_id="owner-a",
    )

    reset_conversation_with_autosave(
        handle,
        updated_at=_UPDATED_AT,
        store=store,
        lock_store=lock_store,
    )

    assert session.conversation.turns == ()
    assert session.updated_at == _UPDATED_AT
    assert session.sync_state is SessionSyncState.CLEAN

    assert store.states[
        session.session_id
    ]["updated_at"] == _UPDATED_AT.isoformat()

    assert lock_store.owners == {
        session.session_id: "owner-a"
    }


def test_reset_persist_failure_keeps_dirty_memory_and_lock() -> None:
    store = FakeSessionStateStore()
    lock_store = FakeSessionLockStore()

    session = _persistent_session(
        sync_state=SessionSyncState.CLEAN,
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

    session.conversation.append(
        turn
    )

    handle = SessionHandle(
        session=session,
        owner_id="owner-a",
    )

    lock_store.owners[
        session.session_id
    ] = "owner-a"

    store.fail_save = True

    with pytest.raises(
        SessionStorageError,
        match="salvar",
    ):
        reset_conversation_with_autosave(
            handle,
            updated_at=_UPDATED_AT,
            store=store,
            lock_store=lock_store,
        )

    assert session.conversation.turns == ()
    assert session.lifecycle is SessionLifecycle.ACTIVE
    assert session.sync_state is SessionSyncState.DIRTY

    assert lock_store.owners == {
        session.session_id: "owner-a"
    }


@pytest.mark.parametrize(
    "lifecycle",
    [
        SessionLifecycle.CLOSED,
        SessionLifecycle.DELETED,
    ],
)
def test_reset_invalid_lifecycle_does_not_acquire_lock_or_write(
    lifecycle: SessionLifecycle,
) -> None:
    store = FakeSessionStateStore()
    lock_store = FakeSessionLockStore()

    session = _persistent_session(
        sync_state=SessionSyncState.CLEAN,
    )
    session.lifecycle = lifecycle

    handle = SessionHandle(
        session=session,
        owner_id="owner-a",
    )

    original_updated_at = session.updated_at

    with pytest.raises(
        SessionLifecycleError,
        match="ACTIVE",
    ):
        reset_conversation_with_autosave(
            handle,
            updated_at=_UPDATED_AT,
            store=store,
            lock_store=lock_store,
        )

    assert session.lifecycle is lifecycle
    assert session.updated_at == original_updated_at
    assert session.sync_state is SessionSyncState.CLEAN
    assert lock_store.owners == {}
    assert store.states == {}


@pytest.mark.parametrize(
    "initial_lifecycle",
    [
        SessionLifecycle.ACTIVE,
        SessionLifecycle.CLOSED,
    ],
)
def test_delete_session_with_autosave_is_logical_and_releases_lock(
    initial_lifecycle: SessionLifecycle,
) -> None:
    store = FakeSessionStateStore()
    lock_store = FakeSessionLockStore()

    session = _persistent_session(
        sync_state=SessionSyncState.CLEAN,
    )
    session.lifecycle = initial_lifecycle

    original_turns = session.conversation.turns

    handle = SessionHandle(
        session=session,
        owner_id="owner-a",
    )

    delete_session_with_autosave(
        handle,
        updated_at=_UPDATED_AT,
        store=store,
        lock_store=lock_store,
    )

    assert session.lifecycle is SessionLifecycle.DELETED
    assert session.updated_at == _UPDATED_AT
    assert session.sync_state is SessionSyncState.CLEAN
    assert session.conversation.turns == original_turns

    stored_state = store.states[
        session.session_id
    ]

    assert stored_state["lifecycle"] == "deleted"

    assert session.session_id in store.states

    assert lock_store.owners == {}


def test_delete_persist_failure_keeps_deleted_dirty_memory_and_lock() -> None:
    store = FakeSessionStateStore()
    lock_store = FakeSessionLockStore()

    session = _persistent_session(
        sync_state=SessionSyncState.CLEAN,
    )

    handle = SessionHandle(
        session=session,
        owner_id="owner-a",
    )

    lock_store.owners[
        session.session_id
    ] = "owner-a"

    store.fail_save = True

    with pytest.raises(
        SessionStorageError,
        match="salvar",
    ):
        delete_session_with_autosave(
            handle,
            updated_at=_UPDATED_AT,
            store=store,
            lock_store=lock_store,
        )

    assert session.lifecycle is SessionLifecycle.DELETED
    assert session.sync_state is SessionSyncState.DIRTY

    assert lock_store.owners == {
        session.session_id: "owner-a"
    }


def test_delete_already_deleted_does_not_acquire_lock_or_write() -> None:
    store = FakeSessionStateStore()
    lock_store = FakeSessionLockStore()

    session = _persistent_session(
        sync_state=SessionSyncState.CLEAN,
    )
    session.lifecycle = SessionLifecycle.DELETED

    handle = SessionHandle(
        session=session,
        owner_id="owner-a",
    )

    original_updated_at = session.updated_at

    with pytest.raises(
        SessionLifecycleError,
        match="DELETED",
    ):
        delete_session_with_autosave(
            handle,
            updated_at=_UPDATED_AT,
            store=store,
            lock_store=lock_store,
        )

    assert session.lifecycle is SessionLifecycle.DELETED
    assert session.updated_at == original_updated_at
    assert session.sync_state is SessionSyncState.CLEAN
    assert lock_store.owners == {}
    assert store.states == {}


@pytest.mark.parametrize(
    "operation",
    [
        close_session_with_autosave,
        reset_conversation_with_autosave,
        delete_session_with_autosave,
    ],
)
def test_persistent_wrappers_reject_ephemeral_handle_before_lock(
    operation,
) -> None:
    store = FakeSessionStateStore()
    lock_store = FakeSessionLockStore()

    session = Session(
        session_id="session-ephemeral",
        conversation=LogicalConversationHistory(),
        persistence_mode=PersistenceMode.EPHEMERAL,
        authority=SessionAuthority.LOCAL,
        profile_mode=ProfileMode.auto(),
        created_at=_CREATED_AT,
        updated_at=_CREATED_AT,
    )

    handle = SessionHandle(
        session=session,
        owner_id="owner-a",
    )

    with pytest.raises(
        SessionNotPersistentError,
        match="EPHEMERAL",
    ):
        operation(
            handle,
            updated_at=_UPDATED_AT,
            store=store,
            lock_store=lock_store,
        )

    assert session.lifecycle is SessionLifecycle.ACTIVE
    assert session.sync_state is SessionSyncState.CLEAN
    assert lock_store.owners == {}
    assert store.states == {}


@pytest.mark.parametrize(
    "operation",
    [
        close_session_with_autosave,
        reset_conversation_with_autosave,
        delete_session_with_autosave,
    ],
)
def test_other_owner_blocks_persistent_mutation(
    operation,
) -> None:
    store = FakeSessionStateStore()
    lock_store = FakeSessionLockStore()

    session = _persistent_session(
        sync_state=SessionSyncState.CLEAN,
    )

    handle = SessionHandle(
        session=session,
        owner_id="owner-b",
    )

    lock_store.owners[
        session.session_id
    ] = "owner-a"

    original_lifecycle = session.lifecycle
    original_updated_at = session.updated_at

    with pytest.raises(
        SessionInUseError,
    ):
        operation(
            handle,
            updated_at=_UPDATED_AT,
            store=store,
            lock_store=lock_store,
        )

    assert session.lifecycle is original_lifecycle
    assert session.updated_at == original_updated_at
    assert session.sync_state is SessionSyncState.CLEAN

    assert lock_store.owners == {
        session.session_id: "owner-a"
    }

    assert store.states == {}


def test_shutdown_clean_session_releases_lock_without_save() -> None:
    store = FakeSessionStateStore()
    lock_store = FakeSessionLockStore()

    session = _persistent_session(
        sync_state=SessionSyncState.CLEAN,
    )

    handle = SessionHandle(
        session=session,
        owner_id="owner-a",
    )

    lock_store.owners[
        session.session_id
    ] = "owner-a"

    original_lifecycle = session.lifecycle
    original_updated_at = session.updated_at
    original_turns = session.conversation.turns

    shutdown_persistent_session(
        handle,
        store=store,
        lock_store=lock_store,
    )

    assert session.lifecycle is original_lifecycle
    assert session.updated_at == original_updated_at
    assert session.conversation.turns == original_turns
    assert session.sync_state is SessionSyncState.CLEAN
    assert store.states == {}
    assert lock_store.owners == {}


def test_shutdown_dirty_session_persists_and_releases_lock() -> None:
    store = FakeSessionStateStore()
    lock_store = FakeSessionLockStore()

    session = _persistent_session(
        sync_state=SessionSyncState.DIRTY,
    )

    handle = SessionHandle(
        session=session,
        owner_id="owner-a",
    )

    lock_store.owners[
        session.session_id
    ] = "owner-a"

    original_lifecycle = session.lifecycle
    original_updated_at = session.updated_at
    original_turns = session.conversation.turns

    shutdown_persistent_session(
        handle,
        store=store,
        lock_store=lock_store,
    )

    assert session.lifecycle is original_lifecycle
    assert session.updated_at == original_updated_at
    assert session.conversation.turns == original_turns
    assert session.sync_state is SessionSyncState.CLEAN
    assert session.session_id in store.states
    assert lock_store.owners == {}


def test_shutdown_persist_failure_keeps_dirty_session_and_lock() -> None:
    store = FakeSessionStateStore()
    lock_store = FakeSessionLockStore()

    session = _persistent_session(
        sync_state=SessionSyncState.DIRTY,
    )

    handle = SessionHandle(
        session=session,
        owner_id="owner-a",
    )

    lock_store.owners[
        session.session_id
    ] = "owner-a"

    store.fail_save = True

    original_lifecycle = session.lifecycle
    original_updated_at = session.updated_at
    original_turns = session.conversation.turns

    with pytest.raises(
        SessionStorageError,
        match="salvar",
    ):
        shutdown_persistent_session(
            handle,
            store=store,
            lock_store=lock_store,
        )

    assert session.lifecycle is original_lifecycle
    assert session.updated_at == original_updated_at
    assert session.conversation.turns == original_turns
    assert session.sync_state is SessionSyncState.DIRTY
    assert store.states == {}
    assert lock_store.owners == {
        session.session_id: "owner-a"
    }


def test_shutdown_release_failure_preserves_persisted_clean_state() -> None:
    store = FakeSessionStateStore()
    lock_store = FakeSessionLockStore()

    session = _persistent_session(
        sync_state=SessionSyncState.DIRTY,
    )

    handle = SessionHandle(
        session=session,
        owner_id="owner-a",
    )

    lock_store.owners[
        session.session_id
    ] = "owner-a"

    lock_store.fail_release = True

    original_lifecycle = session.lifecycle
    original_updated_at = session.updated_at

    with pytest.raises(
        SessionLockOwnershipError,
        match="falha simulada",
    ):
        shutdown_persistent_session(
            handle,
            store=store,
            lock_store=lock_store,
        )

    assert session.lifecycle is original_lifecycle
    assert session.updated_at == original_updated_at
    assert session.sync_state is SessionSyncState.CLEAN
    assert session.session_id in store.states
    assert lock_store.owners == {
        session.session_id: "owner-a"
    }


@pytest.mark.parametrize(
    "lifecycle",
    [
        SessionLifecycle.CLOSED,
        SessionLifecycle.DELETED,
    ],
)
def test_shutdown_invalid_lifecycle_does_not_acquire_lock_or_write(
    lifecycle: SessionLifecycle,
) -> None:
    store = FakeSessionStateStore()
    lock_store = FakeSessionLockStore()

    session = _persistent_session(
        sync_state=SessionSyncState.CLEAN,
    )
    session.lifecycle = lifecycle

    handle = SessionHandle(
        session=session,
        owner_id="owner-a",
    )

    original_updated_at = session.updated_at

    with pytest.raises(
        SessionLifecycleError,
        match="ACTIVE",
    ):
        shutdown_persistent_session(
            handle,
            store=store,
            lock_store=lock_store,
        )

    assert session.lifecycle is lifecycle
    assert session.updated_at == original_updated_at
    assert session.sync_state is SessionSyncState.CLEAN
    assert lock_store.owners == {}
    assert store.states == {}


def test_shutdown_rejects_ephemeral_handle_before_lock_or_write() -> None:
    store = FakeSessionStateStore()
    lock_store = FakeSessionLockStore()

    session = _ephemeral_session()

    handle = SessionHandle(
        session=session,
        owner_id="owner-a",
    )

    original_updated_at = session.updated_at

    with pytest.raises(
        SessionNotPersistentError,
        match="EPHEMERAL",
    ):
        shutdown_persistent_session(
            handle,
            store=store,
            lock_store=lock_store,
        )

    assert session.lifecycle is SessionLifecycle.ACTIVE
    assert session.updated_at == original_updated_at
    assert session.sync_state is SessionSyncState.CLEAN
    assert lock_store.owners == {}
    assert store.states == {}


def test_other_owner_blocks_shutdown_before_persist() -> None:
    store = FakeSessionStateStore()
    lock_store = FakeSessionLockStore()

    session = _persistent_session(
        sync_state=SessionSyncState.DIRTY,
    )

    handle = SessionHandle(
        session=session,
        owner_id="owner-b",
    )

    lock_store.owners[
        session.session_id
    ] = "owner-a"

    original_updated_at = session.updated_at

    with pytest.raises(
        SessionInUseError,
        match="outro owner",
    ):
        shutdown_persistent_session(
            handle,
            store=store,
            lock_store=lock_store,
        )

    assert session.lifecycle is SessionLifecycle.ACTIVE
    assert session.updated_at == original_updated_at
    assert session.sync_state is SessionSyncState.DIRTY
    assert store.states == {}
    assert lock_store.owners == {
        session.session_id: "owner-a"
    }
