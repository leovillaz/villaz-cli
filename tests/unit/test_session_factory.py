from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import pytest

import villaz_cli.session_factory as session_factory
from villaz_cli.session import (
    PersistenceMode,
    ProfileMode,
    ProfileModeKind,
    SessionAuthority,
    SessionLifecycle,
    SessionSyncState,
)
from villaz_cli.session_lock import (
    SessionInUseError,
    SessionLockOwnershipError,
)
from villaz_cli.session_persistence import (
    SessionStorageError,
)


_CREATED_AT = datetime(
    2026,
    9,
    12,
    10,
    30,
    tzinfo=timezone.utc,
)


class FakeSessionStateStore:
    def __init__(self) -> None:
        self.states: dict[str, dict[str, Any]] = {}
        self.fail_save = False
        self.list_calls = 0
        self.purge_calls = 0

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
        return self.states[session_id]

    def list_session_ids(self) -> tuple[str, ...]:
        self.list_calls += 1
        return tuple(self.states)

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


class FakeSessionLockStore:
    def __init__(self) -> None:
        self.owners: dict[str, str] = {}
        self.fail_release = False
        self.acquire_calls = 0
        self.release_calls = 0

    def acquire(
        self,
        *,
        session_id: str,
        owner_id: str,
        pid: int,
    ) -> None:
        self.acquire_calls += 1

        existing_owner = self.owners.get(
            session_id
        )

        if (
            existing_owner is not None
            and existing_owner != owner_id
        ):
            raise SessionInUseError(
                "Session já está em uso."
            )

        self.owners[
            session_id
        ] = owner_id

    def release(
        self,
        *,
        session_id: str,
        owner_id: str,
    ) -> None:
        self.release_calls += 1

        if self.fail_release:
            raise SessionLockOwnershipError(
                "Falha simulada ao liberar lock."
            )

        existing_owner = self.owners.get(
            session_id
        )

        if existing_owner is None:
            return

        if existing_owner != owner_id:
            raise SessionLockOwnershipError(
                "Owner não corresponde ao lock."
            )

        del self.owners[
            session_id
        ]


def test_generate_session_id_returns_uuid4_string() -> None:
    value = session_factory.generate_session_id()

    parsed = UUID(value)

    assert isinstance(
        value,
        str,
    )
    assert parsed.version == 4
    assert str(parsed) == value


def test_generate_owner_id_returns_uuid4_string() -> None:
    value = session_factory.generate_owner_id()

    parsed = UUID(value)

    assert isinstance(
        value,
        str,
    )
    assert parsed.version == 4
    assert str(parsed) == value


def test_generated_session_ids_are_distinct() -> None:
    first = session_factory.generate_session_id()
    second = session_factory.generate_session_id()

    assert first != second


def test_generated_owner_ids_are_distinct() -> None:
    first = session_factory.generate_owner_id()
    second = session_factory.generate_owner_id()

    assert first != second


def test_ephemeral_session_has_expected_initial_state(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        session_factory,
        "generate_session_id",
        lambda: "session-test",
    )

    session = session_factory.create_ephemeral_session(
        created_at=_CREATED_AT,
    )

    assert session.session_id == "session-test"
    assert session.conversation.turns == ()
    assert session.persistence_mode is PersistenceMode.EPHEMERAL
    assert session.authority is SessionAuthority.LOCAL
    assert session.profile_mode.kind is ProfileModeKind.AUTO
    assert session.profile_mode.profile_id is None
    assert session.created_at == _CREATED_AT
    assert session.updated_at == _CREATED_AT
    assert session.lifecycle is SessionLifecycle.ACTIVE
    assert session.sync_state is SessionSyncState.CLEAN


def test_ephemeral_session_preserves_explicit_profile(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        session_factory,
        "generate_session_id",
        lambda: "session-test",
    )

    profile_mode = ProfileMode.explicit(
        "code-review-security"
    )

    session = session_factory.create_ephemeral_session(
        created_at=_CREATED_AT,
        profile_mode=profile_mode,
    )

    assert session.profile_mode == profile_mode


def test_ephemeral_creation_does_not_require_stores() -> None:
    session = session_factory.create_ephemeral_session(
        created_at=_CREATED_AT,
    )

    assert session.persistence_mode is PersistenceMode.EPHEMERAL
    assert session.sync_state is SessionSyncState.CLEAN


def test_persistent_session_is_saved_clean_and_locked(
    monkeypatch,
) -> None:
    store = FakeSessionStateStore()
    lock_store = FakeSessionLockStore()

    monkeypatch.setattr(
        session_factory,
        "generate_session_id",
        lambda: "session-persistent",
    )
    monkeypatch.setattr(
        session_factory,
        "generate_owner_id",
        lambda: "owner-a",
    )

    handle = session_factory.create_persistent_session(
        created_at=_CREATED_AT,
        store=store,
        lock_store=lock_store,
    )

    session = handle.session

    assert handle.owner_id == "owner-a"
    assert session.session_id == "session-persistent"
    assert session.conversation.turns == ()
    assert session.persistence_mode is PersistenceMode.PERSISTENT
    assert session.authority is SessionAuthority.LOCAL
    assert session.lifecycle is SessionLifecycle.ACTIVE
    assert session.sync_state is SessionSyncState.CLEAN
    assert session.created_at == _CREATED_AT
    assert session.updated_at == _CREATED_AT

    assert lock_store.owners == {
        "session-persistent": "owner-a"
    }

    assert store.states[
        "session-persistent"
    ]["session_id"] == "session-persistent"

    assert store.states[
        "session-persistent"
    ]["lifecycle"] == "active"


def test_persistent_session_preserves_explicit_profile(
    monkeypatch,
) -> None:
    store = FakeSessionStateStore()
    lock_store = FakeSessionLockStore()

    monkeypatch.setattr(
        session_factory,
        "generate_session_id",
        lambda: "session-persistent",
    )
    monkeypatch.setattr(
        session_factory,
        "generate_owner_id",
        lambda: "owner-a",
    )

    profile_mode = ProfileMode.explicit(
        "code-review-security"
    )

    handle = session_factory.create_persistent_session(
        created_at=_CREATED_AT,
        store=store,
        lock_store=lock_store,
        profile_mode=profile_mode,
    )

    assert handle.session.profile_mode == profile_mode

    stored_profile = store.states[
        "session-persistent"
    ]["profile_mode"]

    assert stored_profile["kind"] == "explicit"
    assert stored_profile["profile_id"] == "code-review-security"


def test_session_and_owner_identity_are_independent(
    monkeypatch,
) -> None:
    store = FakeSessionStateStore()
    lock_store = FakeSessionLockStore()

    monkeypatch.setattr(
        session_factory,
        "generate_session_id",
        lambda: "session-id",
    )
    monkeypatch.setattr(
        session_factory,
        "generate_owner_id",
        lambda: "owner-id",
    )

    handle = session_factory.create_persistent_session(
        created_at=_CREATED_AT,
        store=store,
        lock_store=lock_store,
    )

    assert handle.session.session_id == "session-id"
    assert handle.owner_id == "owner-id"
    assert handle.session.session_id != handle.owner_id


def test_persistent_creation_does_not_list_or_purge(
    monkeypatch,
) -> None:
    store = FakeSessionStateStore()
    lock_store = FakeSessionLockStore()

    monkeypatch.setattr(
        session_factory,
        "generate_session_id",
        lambda: "session-persistent",
    )
    monkeypatch.setattr(
        session_factory,
        "generate_owner_id",
        lambda: "owner-a",
    )

    session_factory.create_persistent_session(
        created_at=_CREATED_AT,
        store=store,
        lock_store=lock_store,
    )

    assert store.list_calls == 0
    assert store.purge_calls == 0


def test_lock_conflict_prevents_persistent_write(
    monkeypatch,
) -> None:
    store = FakeSessionStateStore()
    lock_store = FakeSessionLockStore()

    lock_store.owners[
        "session-conflict"
    ] = "owner-existing"

    monkeypatch.setattr(
        session_factory,
        "generate_session_id",
        lambda: "session-conflict",
    )
    monkeypatch.setattr(
        session_factory,
        "generate_owner_id",
        lambda: "owner-new",
    )

    with pytest.raises(
        SessionInUseError,
    ):
        session_factory.create_persistent_session(
            created_at=_CREATED_AT,
            store=store,
            lock_store=lock_store,
        )

    assert store.states == {}

    assert lock_store.owners == {
        "session-conflict": "owner-existing"
    }

    assert lock_store.release_calls == 0


def test_persist_failure_releases_new_lock(
    monkeypatch,
) -> None:
    store = FakeSessionStateStore()
    lock_store = FakeSessionLockStore()

    store.fail_save = True

    monkeypatch.setattr(
        session_factory,
        "generate_session_id",
        lambda: "session-failure",
    )
    monkeypatch.setattr(
        session_factory,
        "generate_owner_id",
        lambda: "owner-a",
    )

    with pytest.raises(
        SessionStorageError,
        match="salvar",
    ):
        session_factory.create_persistent_session(
            created_at=_CREATED_AT,
            store=store,
            lock_store=lock_store,
        )

    assert store.states == {}
    assert lock_store.owners == {}
    assert lock_store.release_calls == 1


def test_cleanup_failure_preserves_original_persistence_error(
    monkeypatch,
) -> None:
    store = FakeSessionStateStore()
    lock_store = FakeSessionLockStore()

    store.fail_save = True
    lock_store.fail_release = True

    monkeypatch.setattr(
        session_factory,
        "generate_session_id",
        lambda: "session-failure",
    )
    monkeypatch.setattr(
        session_factory,
        "generate_owner_id",
        lambda: "owner-a",
    )

    with pytest.raises(
        SessionStorageError,
        match="salvar",
    ) as exc_info:
        session_factory.create_persistent_session(
            created_at=_CREATED_AT,
            store=store,
            lock_store=lock_store,
        )

    assert any(
        "Falha adicional ao liberar o lock"
        in note
        for note in exc_info.value.__notes__
    )

    assert lock_store.owners == {
        "session-failure": "owner-a"
    }


def test_persistent_creation_returns_locked_handle_only_after_save(
    monkeypatch,
) -> None:
    store = FakeSessionStateStore()
    lock_store = FakeSessionLockStore()

    monkeypatch.setattr(
        session_factory,
        "generate_session_id",
        lambda: "session-persistent",
    )
    monkeypatch.setattr(
        session_factory,
        "generate_owner_id",
        lambda: "owner-a",
    )

    handle = session_factory.create_persistent_session(
        created_at=_CREATED_AT,
        store=store,
        lock_store=lock_store,
    )

    assert handle.session.sync_state is SessionSyncState.CLEAN
    assert "session-persistent" in store.states
    assert lock_store.owners[
        "session-persistent"
    ] == handle.owner_id
