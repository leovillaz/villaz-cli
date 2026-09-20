from typing import Any, Protocol
from datetime import datetime
from villaz_cli.conversation import (
    ConversationResult,
    Turn,
)
from dataclasses import dataclass

from villaz_cli.session import (
    ConversationRequest,
    PersistenceMode,
    ProfileMode,
    Session,
    SessionLifecycle,
    SessionLifecycleError,
    SessionSyncState,
)
from villaz_cli.session_state import (
    session_from_state,
    session_to_state,
)
from villaz_cli.session_lock import (
    SessionLockError,
    SessionLockStore,
    acquire_session_lock,
    release_session_lock,
)


class SessionPersistenceError(Exception):
    """Base error for Session persistence operations."""


class SessionNotPersistentError(SessionPersistenceError):
    """Raised when persistence is requested for an ephemeral Session."""


class SessionNotFoundError(SessionPersistenceError):
    """Raised when a persisted Session cannot be found."""


class SessionStorageError(SessionPersistenceError):
    """Raised when the persistence backend cannot complete an operation."""


class SessionIdentityMismatchError(SessionPersistenceError):
    """Raised when loaded state does not match the requested Session identity."""


class SessionPromotionError(SessionPersistenceError):
    """Raised when an ephemeral Session cannot be promoted."""


class SessionDeletedError(SessionPersistenceError):
    """Raised when a deleted Session is requested for resume."""


@dataclass(frozen=True, slots=True)
class SessionHandle:
    session: Session
    owner_id: str


class SessionStateStore(Protocol):
    def save(
        self,
        *,
        session_id: str,
        state: dict[str, Any],
    ) -> None:
        ...

    def load(
        self,
        *,
        session_id: str,
    ) -> dict[str, Any]:
        ...

    def list_session_ids(self) -> tuple[str, ...]:
        ...

    def purge(
        self,
        *,
        session_id: str,
    ) -> None:
        ...


def persist_session(
    session: Session,
    *,
    store: SessionStateStore,
) -> None:
    if session.persistence_mode is not PersistenceMode.PERSISTENT:
        raise SessionNotPersistentError(
            "Uma Session EPHEMERAL não pode ser persistida."
        )

    state = session_to_state(session)

    store.save(
        session_id=session.session_id,
        state=state,
    )

    session.mark_clean()


def commit_turn_with_autosave(
    session: Session,
    turn: Turn,
    *,
    updated_at: datetime,
    store: SessionStateStore,
) -> None:
    session.commit_turn(
        turn,
        updated_at=updated_at,
    )

    if session.persistence_mode is PersistenceMode.PERSISTENT:
        persist_session(
            session,
            store=store,
        )


def commit_conversation_result_with_autosave(
    session: Session,
    request: ConversationRequest,
    result: ConversationResult,
    *,
    updated_at: datetime,
    store: SessionStateStore,
) -> Turn | None:
    turn = request.materialize_turn(
        result
    )

    if turn is None:
        return None

    commit_turn_with_autosave(
        session,
        turn,
        updated_at=updated_at,
        store=store,
    )

    return turn


def change_profile_mode_with_autosave(
    session: Session,
    profile_mode: ProfileMode,
    *,
    updated_at: datetime,
    store: SessionStateStore,
) -> None:
    session.change_profile_mode(
        profile_mode,
        updated_at=updated_at,
    )

    if session.persistence_mode is PersistenceMode.PERSISTENT:
        persist_session(
            session,
            store=store,
        )


def promote_to_persistent(
    session: Session,
    *,
    store: SessionStateStore,
) -> None:
    if session.lifecycle is not SessionLifecycle.ACTIVE:
        raise SessionPromotionError(
            "Somente uma Session ACTIVE pode ser promovida."
        )

    if session.persistence_mode is not PersistenceMode.EPHEMERAL:
        raise SessionPromotionError(
            "Somente uma Session EPHEMERAL pode ser promovida."
        )

    candidate = Session(
        session_id=session.session_id,
        conversation=session.conversation,
        persistence_mode=PersistenceMode.PERSISTENT,
        authority=session.authority,
        profile_mode=session.profile_mode,
        created_at=session.created_at,
        updated_at=session.updated_at,
        lifecycle=session.lifecycle,
        sync_state=SessionSyncState.CLEAN,
    )

    state = session_to_state(candidate)

    store.save(
        session_id=session.session_id,
        state=state,
    )

    session.persistence_mode = PersistenceMode.PERSISTENT
    session.sync_state = SessionSyncState.CLEAN


def load_session(
    session_id: str,
    *,
    store: SessionStateStore,
) -> Session:
    state = store.load(
        session_id=session_id,
    )

    session = session_from_state(state)

    if session.session_id != session_id:
        raise SessionIdentityMismatchError(
            "A identidade da Session carregada não corresponde à solicitada."
        )

    return session


def resume_session(
    session_id: str,
    *,
    owner_id: str,
    updated_at: datetime,
    store: SessionStateStore,
    lock_store: SessionLockStore,
) -> SessionHandle:
    acquire_session_lock(
        session_id,
        owner_id=owner_id,
        store=lock_store,
    )

    try:
        session = load_session(
            session_id,
            store=store,
        )

        if session.lifecycle is SessionLifecycle.DELETED:
            raise SessionDeletedError(
                "Uma Session DELETED não pode ser retomada."
            )

        if session.lifecycle is SessionLifecycle.CLOSED:
            session.resume(
                updated_at=updated_at,
            )

            persist_session(
                session,
                store=store,
            )

        return SessionHandle(
            session=session,
            owner_id=owner_id,
        )

    except Exception as exc:
        try:
            release_session_lock(
                session_id,
                owner_id=owner_id,
                store=lock_store,
            )
        except SessionLockError as cleanup_exc:
            exc.add_note(
                "Falha adicional ao liberar o lock após erro de resume: "
                f"{cleanup_exc}"
            )

        raise


def _require_persistent_handle(
    handle: SessionHandle,
) -> Session:
    session = handle.session

    if session.persistence_mode is not PersistenceMode.PERSISTENT:
        raise SessionNotPersistentError(
            "Uma Session EPHEMERAL não pode usar operações persistentes."
        )

    return session


def _acquire_handle_lock(
    handle: SessionHandle,
    *,
    lock_store: SessionLockStore,
) -> None:
    acquire_session_lock(
        handle.session.session_id,
        owner_id=handle.owner_id,
        store=lock_store,
    )


def close_session_with_autosave(
    handle: SessionHandle,
    *,
    updated_at: datetime,
    store: SessionStateStore,
    lock_store: SessionLockStore,
) -> None:
    session = _require_persistent_handle(
        handle
    )

    if session.lifecycle is not SessionLifecycle.ACTIVE:
        raise SessionLifecycleError(
            "Somente uma Session ACTIVE pode ser fechada."
        )

    _acquire_handle_lock(
        handle,
        lock_store=lock_store,
    )

    session.close(
        updated_at=updated_at,
    )

    persist_session(
        session,
        store=store,
    )

    release_session_lock(
        session.session_id,
        owner_id=handle.owner_id,
        store=lock_store,
    )


def reset_conversation_with_autosave(
    handle: SessionHandle,
    *,
    updated_at: datetime,
    store: SessionStateStore,
    lock_store: SessionLockStore,
) -> None:
    session = _require_persistent_handle(
        handle
    )

    if session.lifecycle is not SessionLifecycle.ACTIVE:
        raise SessionLifecycleError(
            "Somente uma Session ACTIVE pode resetar a Conversation."
        )

    _acquire_handle_lock(
        handle,
        lock_store=lock_store,
    )

    session.reset_conversation(
        updated_at=updated_at,
    )

    persist_session(
        session,
        store=store,
    )


def delete_session_with_autosave(
    handle: SessionHandle,
    *,
    updated_at: datetime,
    store: SessionStateStore,
    lock_store: SessionLockStore,
) -> None:
    session = _require_persistent_handle(
        handle
    )

    if session.lifecycle is SessionLifecycle.DELETED:
        raise SessionLifecycleError(
            "Uma Session DELETED não pode ser excluída novamente."
        )

    _acquire_handle_lock(
        handle,
        lock_store=lock_store,
    )

    session.delete(
        updated_at=updated_at,
    )

    persist_session(
        session,
        store=store,
    )

    release_session_lock(
        session.session_id,
        owner_id=handle.owner_id,
        store=lock_store,
    )


def shutdown_persistent_session(
    handle: SessionHandle,
    *,
    store: SessionStateStore,
    lock_store: SessionLockStore,
) -> None:
    session = _require_persistent_handle(
        handle
    )

    if session.lifecycle is not SessionLifecycle.ACTIVE:
        raise SessionLifecycleError(
            "Somente uma Session ACTIVE pode executar shutdown persistente."
        )

    _acquire_handle_lock(
        handle,
        lock_store=lock_store,
    )

    if session.sync_state is SessionSyncState.DIRTY:
        persist_session(
            session,
            store=store,
        )

    release_session_lock(
        session.session_id,
        owner_id=handle.owner_id,
        store=lock_store,
    )


def list_persisted_session_ids(
    *,
    store: SessionStateStore,
) -> tuple[str, ...]:
    return store.list_session_ids()


def purge_persisted_session(
    session_id: str,
    *,
    store: SessionStateStore,
) -> None:
    store.purge(
        session_id=session_id,
    )
