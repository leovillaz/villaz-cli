from dataclasses import dataclass
from datetime import datetime

from villaz_cli.session import (
    PersistenceMode,
    ProfileMode,
    Session,
    SessionAuthority,
    SessionLifecycle,
)
from villaz_cli.session_persistence import (
    SessionStateStore,
    list_persisted_session_ids,
    load_session,
)


@dataclass(frozen=True, slots=True)
class SessionSummary:
    session_id: str
    lifecycle: SessionLifecycle
    persistence_mode: PersistenceMode
    authority: SessionAuthority
    profile_mode: ProfileMode
    created_at: datetime
    updated_at: datetime
    turn_count: int


def summarize_session(
    session: Session,
) -> SessionSummary:
    return SessionSummary(
        session_id=session.session_id,
        lifecycle=session.lifecycle,
        persistence_mode=session.persistence_mode,
        authority=session.authority,
        profile_mode=session.profile_mode,
        created_at=session.created_at,
        updated_at=session.updated_at,
        turn_count=len(
            session.conversation.turns
        ),
    )


def list_persisted_sessions(
    *,
    store: SessionStateStore,
) -> tuple[SessionSummary, ...]:
    summaries = [
        summarize_session(
            load_session(
                session_id,
                store=store,
            )
        )
        for session_id in list_persisted_session_ids(
            store=store,
        )
    ]

    summaries.sort(
        key=lambda item: item.session_id,
    )
    summaries.sort(
        key=lambda item: item.updated_at,
        reverse=True,
    )

    return tuple(summaries)


def inspect_persisted_session(
    session_id: str,
    *,
    store: SessionStateStore,
) -> SessionSummary:
    session = load_session(
        session_id,
        store=store,
    )

    return summarize_session(
        session
    )
