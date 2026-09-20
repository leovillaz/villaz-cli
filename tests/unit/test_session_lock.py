import hashlib
import json
import os
import stat
from pathlib import Path

import pytest

from villaz_cli.session_lock import (
    JsonSessionLockStore,
    SESSION_LOCK_VERSION,
    SessionInUseError,
    SessionLockCorruptError,
    SessionLockError,
    SessionLockOwnershipError,
)


def _lock_path(
    root: Path,
    session_id: str,
) -> Path:
    key = hashlib.sha256(
        session_id.encode("utf-8")
    ).hexdigest()

    return root / f"{key}.lock"


def test_acquire_creates_hashed_lock_file(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sessions"

    store = JsonSessionLockStore(
        root,
        process_exists=lambda pid: True,
    )

    store.acquire(
        session_id="session-test",
        owner_id="owner-a",
        pid=1001,
    )

    target = _lock_path(
        root,
        "session-test",
    )

    assert target.is_file()
    assert not (
        root / "session-test.lock"
    ).exists()


def test_lock_contains_only_operational_metadata(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sessions"

    store = JsonSessionLockStore(
        root,
        process_exists=lambda pid: True,
    )

    store.acquire(
        session_id="session-test",
        owner_id="owner-a",
        pid=1001,
    )

    payload = json.loads(
        _lock_path(
            root,
            "session-test",
        ).read_text(
            encoding="utf-8"
        )
    )

    assert payload == {
        "lock_version": SESSION_LOCK_VERSION,
        "owner_id": "owner-a",
        "pid": 1001,
        "session_id": "session-test",
    }


def test_same_owner_acquire_is_idempotent(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sessions"

    store = JsonSessionLockStore(
        root,
        process_exists=lambda pid: True,
    )

    store.acquire(
        session_id="session-test",
        owner_id="owner-a",
        pid=1001,
    )

    original = _lock_path(
        root,
        "session-test",
    ).read_bytes()

    store.acquire(
        session_id="session-test",
        owner_id="owner-a",
        pid=1001,
    )

    assert _lock_path(
        root,
        "session-test",
    ).read_bytes() == original


def test_live_other_owner_blocks_acquisition(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sessions"

    store = JsonSessionLockStore(
        root,
        process_exists=lambda pid: True,
    )

    store.acquire(
        session_id="session-test",
        owner_id="owner-a",
        pid=1001,
    )

    with pytest.raises(
        SessionInUseError,
        match="outro owner",
    ):
        store.acquire(
            session_id="session-test",
            owner_id="owner-b",
            pid=1002,
        )


def test_stale_other_owner_is_recovered(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sessions"

    live_pids: set[int] = set()

    store = JsonSessionLockStore(
        root,
        process_exists=lambda pid: pid in live_pids,
    )

    store.acquire(
        session_id="session-test",
        owner_id="owner-a",
        pid=1001,
    )

    live_pids.add(1002)

    store.acquire(
        session_id="session-test",
        owner_id="owner-b",
        pid=1002,
    )

    payload = json.loads(
        _lock_path(
            root,
            "session-test",
        ).read_text(
            encoding="utf-8"
        )
    )

    assert payload["owner_id"] == "owner-b"
    assert payload["pid"] == 1002


def test_release_by_owner_removes_lock(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sessions"

    store = JsonSessionLockStore(root)

    store.acquire(
        session_id="session-test",
        owner_id="owner-a",
        pid=os.getpid(),
    )

    store.release(
        session_id="session-test",
        owner_id="owner-a",
    )

    assert not _lock_path(
        root,
        "session-test",
    ).exists()


def test_release_missing_lock_is_idempotent(
    tmp_path: Path,
) -> None:
    store = JsonSessionLockStore(
        tmp_path / "sessions"
    )

    store.release(
        session_id="session-test",
        owner_id="owner-a",
    )


def test_other_owner_cannot_release_lock(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sessions"

    store = JsonSessionLockStore(root)

    store.acquire(
        session_id="session-test",
        owner_id="owner-a",
        pid=os.getpid(),
    )

    with pytest.raises(
        SessionLockOwnershipError,
        match="outro owner",
    ):
        store.release(
            session_id="session-test",
            owner_id="owner-b",
        )

    assert _lock_path(
        root,
        "session-test",
    ).exists()


def test_opaque_session_id_is_not_used_as_path(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sessions"

    store = JsonSessionLockStore(root)

    session_id = "../outside\\session:test"

    store.acquire(
        session_id=session_id,
        owner_id="owner-a",
        pid=os.getpid(),
    )

    assert _lock_path(
        root,
        session_id,
    ).is_file()

    assert not (
        tmp_path / "outside"
    ).exists()


def test_invalid_json_lock_is_explicit_corruption(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sessions"
    root.mkdir()

    target = _lock_path(
        root,
        "session-test",
    )

    target.write_text(
        '{"lock_version":',
        encoding="utf-8",
    )

    store = JsonSessionLockStore(root)

    with pytest.raises(
        SessionLockCorruptError,
        match="JSON",
    ):
        store.acquire(
            session_id="session-test",
            owner_id="owner-a",
            pid=os.getpid(),
        )


def test_invalid_lock_pid_is_explicit_corruption(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sessions"
    root.mkdir()

    target = _lock_path(
        root,
        "session-test",
    )

    target.write_text(
        json.dumps(
            {
                "lock_version": SESSION_LOCK_VERSION,
                "session_id": "session-test",
                "owner_id": "owner-a",
                "pid": 0,
            }
        ),
        encoding="utf-8",
    )

    store = JsonSessionLockStore(root)

    with pytest.raises(
        SessionLockCorruptError,
        match="pid",
    ):
        store.acquire(
            session_id="session-test",
            owner_id="owner-b",
            pid=os.getpid(),
        )


def test_lock_identity_mismatch_is_explicit_corruption(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sessions"
    root.mkdir()

    target = _lock_path(
        root,
        "session-test",
    )

    target.write_text(
        json.dumps(
            {
                "lock_version": SESSION_LOCK_VERSION,
                "session_id": "other-session",
                "owner_id": "owner-a",
                "pid": os.getpid(),
            }
        ),
        encoding="utf-8",
    )

    store = JsonSessionLockStore(root)

    with pytest.raises(
        SessionLockCorruptError,
        match="identidade",
    ):
        store.acquire(
            session_id="session-test",
            owner_id="owner-b",
            pid=os.getpid(),
        )


def test_root_existing_as_file_is_lock_error(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sessions"

    root.write_text(
        "not a directory",
        encoding="utf-8",
    )

    store = JsonSessionLockStore(root)

    with pytest.raises(
        SessionLockError,
        match="arquivo",
    ):
        store.acquire(
            session_id="session-test",
            owner_id="owner-a",
            pid=os.getpid(),
        )


@pytest.mark.skipif(
    os.name == "nt",
    reason="Permissões POSIX não possuem semântica equivalente no Windows.",
)
def test_lock_uses_restrictive_posix_permissions(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sessions"

    store = JsonSessionLockStore(root)

    store.acquire(
        session_id="session-test",
        owner_id="owner-a",
        pid=os.getpid(),
    )

    root_mode = stat.S_IMODE(
        root.stat().st_mode
    )

    file_mode = stat.S_IMODE(
        _lock_path(
            root,
            "session-test",
        ).stat().st_mode
    )

    assert root_mode == 0o700
    assert file_mode == 0o600


@pytest.mark.skipif(
    os.name == "nt",
    reason="Teste de symlink restrito ao gate POSIX.",
)
def test_lock_symlink_is_rejected(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sessions"
    root.mkdir()

    outside = tmp_path / "outside.lock"

    outside.write_text(
        "{}",
        encoding="utf-8",
    )

    target = _lock_path(
        root,
        "session-test",
    )

    target.symlink_to(
        outside
    )

    store = JsonSessionLockStore(root)

    with pytest.raises(
        SessionLockCorruptError,
        match="symlink",
    ):
        store.acquire(
            session_id="session-test",
            owner_id="owner-a",
            pid=os.getpid(),
        )
