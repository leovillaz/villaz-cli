import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any

import pytest

from villaz_cli.session_file_store import (
    JsonSessionStateStore,
    SessionCorruptStateError,
)
from villaz_cli.session_persistence import (
    SessionNotFoundError,
    SessionStorageError,
)


def _storage_key(
    session_id: str,
) -> str:
    return hashlib.sha256(
        session_id.encode("utf-8")
    ).hexdigest()


def _state(
    session_id: str = "session-test",
    *,
    response: str = "Olá!",
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "session_id": session_id,
        "conversation": {
            "turns": [
                {
                    "user": {
                        "role": "user",
                        "content": "Olá",
                    },
                    "assistant": {
                        "role": "assistant",
                        "content": response,
                    },
                }
            ]
        },
    }


def _target(
    root: Path,
    session_id: str,
) -> Path:
    return root / (
        f"{_storage_key(session_id)}.json"
    )


def test_save_creates_root_and_hashed_json_file(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sessions"
    store = JsonSessionStateStore(root)

    store.save(
        session_id="session-test",
        state=_state(),
    )

    assert root.is_dir()

    target = _target(
        root,
        "session-test",
    )

    assert target.is_file()
    assert not (
        root / "session-test.json"
    ).exists()


def test_filename_does_not_use_opaque_session_id_directly(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sessions"
    store = JsonSessionStateStore(root)

    session_id = "../outside\\session:test"

    store.save(
        session_id=session_id,
        state=_state(session_id),
    )

    assert _target(
        root,
        session_id,
    ).is_file()

    assert not (
        tmp_path / "outside"
    ).exists()


def test_save_writes_deterministic_utf8_json(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sessions"
    store = JsonSessionStateStore(root)

    state = {
        "z": "ação",
        "a": 1,
        "session_id": "session-test",
    }

    store.save(
        session_id="session-test",
        state=state,
    )

    expected = (
        json.dumps(
            state,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")

    assert _target(
        root,
        "session-test",
    ).read_bytes() == expected


def test_save_calls_fsync_before_replace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "sessions"
    store = JsonSessionStateStore(root)

    calls: list[int] = []

    original_fsync = os.fsync

    def recording_fsync(
        fd: int,
    ) -> None:
        calls.append(fd)
        original_fsync(fd)

    monkeypatch.setattr(
        os,
        "fsync",
        recording_fsync,
    )

    store.save(
        session_id="session-test",
        state=_state(),
    )

    assert len(calls) == 1


def test_replace_failure_preserves_previous_authoritative_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "sessions"
    store = JsonSessionStateStore(root)

    store.save(
        session_id="session-test",
        state=_state(
            response="resposta antiga"
        ),
    )

    target = _target(
        root,
        "session-test",
    )
    original_bytes = target.read_bytes()

    def fail_replace(
        source: object,
        destination: object,
    ) -> None:
        raise OSError(
            "falha simulada"
        )

    monkeypatch.setattr(
        os,
        "replace",
        fail_replace,
    )

    with pytest.raises(
        SessionStorageError,
        match="atomicamente",
    ):
        store.save(
            session_id="session-test",
            state=_state(
                response="resposta nova"
            ),
        )

    assert target.read_bytes() == original_bytes
    assert list(
        root.glob("*.tmp")
    ) == []


def test_save_replaces_existing_state(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sessions"
    store = JsonSessionStateStore(root)

    store.save(
        session_id="session-test",
        state=_state(
            response="antiga"
        ),
    )

    store.save(
        session_id="session-test",
        state=_state(
            response="nova"
        ),
    )

    loaded = store.load(
        session_id="session-test",
    )

    assert (
        loaded["conversation"]["turns"][0]["assistant"]["content"]
        == "nova"
    )


def test_load_returns_json_object(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sessions"
    store = JsonSessionStateStore(root)

    state = _state()

    store.save(
        session_id="session-test",
        state=state,
    )

    assert store.load(
        session_id="session-test",
    ) == state


def test_load_missing_root_is_not_found(
    tmp_path: Path,
) -> None:
    store = JsonSessionStateStore(
        tmp_path / "missing"
    )

    with pytest.raises(
        SessionNotFoundError,
        match="não encontrada",
    ):
        store.load(
            session_id="session-test",
        )


def test_load_missing_session_is_not_found(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sessions"
    root.mkdir()

    store = JsonSessionStateStore(root)

    with pytest.raises(
        SessionNotFoundError,
        match="não encontrada",
    ):
        store.load(
            session_id="session-test",
        )


def test_invalid_utf8_is_corrupt_state(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sessions"
    root.mkdir()

    target = _target(
        root,
        "session-test",
    )
    target.write_bytes(
        b"\xff\xfe\xfa"
    )

    store = JsonSessionStateStore(root)

    with pytest.raises(
        SessionCorruptStateError,
        match="UTF-8",
    ):
        store.load(
            session_id="session-test",
        )


def test_invalid_json_is_corrupt_state(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sessions"
    root.mkdir()

    target = _target(
        root,
        "session-test",
    )
    target.write_text(
        '{"session_id":',
        encoding="utf-8",
    )

    store = JsonSessionStateStore(root)

    with pytest.raises(
        SessionCorruptStateError,
        match="JSON",
    ):
        store.load(
            session_id="session-test",
        )


def test_non_object_json_root_is_corrupt_state(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sessions"
    root.mkdir()

    target = _target(
        root,
        "session-test",
    )
    target.write_text(
        "[]\n",
        encoding="utf-8",
    )

    store = JsonSessionStateStore(root)

    with pytest.raises(
        SessionCorruptStateError,
        match="raiz",
    ):
        store.load(
            session_id="session-test",
        )


def test_list_missing_root_is_empty(
    tmp_path: Path,
) -> None:
    store = JsonSessionStateStore(
        tmp_path / "missing"
    )

    assert store.list_session_ids() == ()


def test_list_returns_session_ids_in_lexical_order(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sessions"
    store = JsonSessionStateStore(root)

    store.save(
        session_id="session-b",
        state=_state("session-b"),
    )
    store.save(
        session_id="session-a",
        state=_state("session-a"),
    )

    assert store.list_session_ids() == (
        "session-a",
        "session-b",
    )


def test_list_ignores_non_json_and_temp_files(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sessions"
    store = JsonSessionStateStore(root)

    store.save(
        session_id="session-test",
        state=_state(),
    )

    (
        root / "notes.txt"
    ).write_text(
        "ignore",
        encoding="utf-8",
    )

    (
        root / ".orphan.tmp"
    ).write_text(
        "ignore",
        encoding="utf-8",
    )

    assert store.list_session_ids() == (
        "session-test",
    )


def test_list_rejects_json_without_valid_session_id(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sessions"
    root.mkdir()

    rogue = root / (
        f"{'0' * 64}.json"
    )
    rogue.write_text(
        '{"schema_version":1}\n',
        encoding="utf-8",
    )

    store = JsonSessionStateStore(root)

    with pytest.raises(
        SessionCorruptStateError,
        match="session_id",
    ):
        store.list_session_ids()


def test_list_rejects_filename_identity_mismatch(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sessions"
    store = JsonSessionStateStore(root)

    store.save(
        session_id="session-a",
        state=_state("session-a"),
    )

    original = _target(
        root,
        "session-a",
    )
    mismatched = _target(
        root,
        "session-b",
    )

    original.rename(
        mismatched
    )

    with pytest.raises(
        SessionCorruptStateError,
        match="filename",
    ):
        store.list_session_ids()


def test_purge_removes_only_requested_state(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sessions"
    store = JsonSessionStateStore(root)

    store.save(
        session_id="session-a",
        state=_state("session-a"),
    )
    store.save(
        session_id="session-b",
        state=_state("session-b"),
    )

    store.purge(
        session_id="session-a",
    )

    assert not _target(
        root,
        "session-a",
    ).exists()

    assert _target(
        root,
        "session-b",
    ).is_file()


def test_purge_missing_session_is_not_found(
    tmp_path: Path,
) -> None:
    store = JsonSessionStateStore(
        tmp_path / "sessions"
    )

    with pytest.raises(
        SessionNotFoundError,
    ):
        store.purge(
            session_id="missing-session",
        )


def test_root_existing_as_file_is_storage_error(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sessions"
    root.write_text(
        "not a directory",
        encoding="utf-8",
    )

    store = JsonSessionStateStore(root)

    with pytest.raises(
        SessionStorageError,
        match="arquivo",
    ):
        store.save(
            session_id="session-test",
            state=_state(),
        )


@pytest.mark.skipif(
    os.name == "nt",
    reason="Permissões POSIX não possuem semântica equivalente no Windows.",
)
def test_created_root_and_file_have_restrictive_posix_permissions(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sessions"
    store = JsonSessionStateStore(root)

    store.save(
        session_id="session-test",
        state=_state(),
    )

    root_mode = stat.S_IMODE(
        root.stat().st_mode
    )
    file_mode = stat.S_IMODE(
        _target(
            root,
            "session-test",
        ).stat().st_mode
    )

    assert root_mode == 0o700
    assert file_mode == 0o600


@pytest.mark.skipif(
    os.name == "nt",
    reason="Teste de symlink restrito ao gate POSIX desta suíte.",
)
def test_load_rejects_session_target_symlink(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sessions"
    root.mkdir()

    outside = tmp_path / "outside.json"
    outside.write_text(
        json.dumps(
            _state()
        ),
        encoding="utf-8",
    )

    target = _target(
        root,
        "session-test",
    )
    target.symlink_to(
        outside
    )

    store = JsonSessionStateStore(root)

    with pytest.raises(
        SessionStorageError,
        match="symlink",
    ):
        store.load(
            session_id="session-test",
        )


def test_unserializable_state_is_storage_error(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sessions"
    store = JsonSessionStateStore(root)

    state = _state()
    state["invalid"] = object()

    with pytest.raises(
        SessionStorageError,
        match="serializado",
    ):
        store.save(
            session_id="session-test",
            state=state,
        )

    assert not root.exists() or list(
        root.glob("*.json")
    ) == []
