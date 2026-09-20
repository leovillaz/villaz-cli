import uuid
from datetime import datetime

from villaz_cli.conversation import LogicalConversationHistory
from villaz_cli.session import (
    PersistenceMode,
    ProfileMode,
    Session,
    SessionAuthority,
    SessionLifecycle,
    SessionSyncState,
)
from villaz_cli.session_lock import (
    SessionLockError,
    SessionLockStore,
    acquire_session_lock,
    release_session_lock,
)
from villaz_cli.session_persistence import (
    SessionHandle,
    SessionStateStore,
    persist_session,
)


def generate_session_id() -> str:
    return str(uuid.uuid4())


def generate_owner_id() -> str:
    return str(uuid.uuid4())


def create_ephemeral_session(
    *,
    created_at: datetime,
    profile_mode: ProfileMode | None = None,
) -> Session:
    return Session(
        session_id=generate_session_id(),
        conversation=LogicalConversationHistory(),
        persistence_mode=PersistenceMode.EPHEMERAL,
        authority=SessionAuthority.LOCAL,
        profile_mode=profile_mode or ProfileMode.auto(),
        created_at=created_at,
        updated_at=created_at,
        lifecycle=SessionLifecycle.ACTIVE,
        sync_state=SessionSyncState.CLEAN,
    )


def create_persistent_session(
    *,
    created_at: datetime,
    store: SessionStateStore,
    lock_store: SessionLockStore,
    profile_mode: ProfileMode | None = None,
) -> SessionHandle:
    session_id = generate_session_id()
    owner_id = generate_owner_id()

    session = Session(
        session_id=session_id,
        conversation=LogicalConversationHistory(),
        persistence_mode=PersistenceMode.PERSISTENT,
        authority=SessionAuthority.LOCAL,
        profile_mode=profile_mode or ProfileMode.auto(),
        created_at=created_at,
        updated_at=created_at,
        lifecycle=SessionLifecycle.ACTIVE,
        sync_state=SessionSyncState.DIRTY,
    )

    acquire_session_lock(
        session_id,
        owner_id=owner_id,
        store=lock_store,
    )

    try:
        persist_session(
            session,
            store=store,
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
                "Falha adicional ao liberar o lock após erro "
                "na criação persistente: "
                f"{cleanup_exc}"
            )

        raise

    return SessionHandle(
        session=session,
        owner_id=owner_id,
    )
