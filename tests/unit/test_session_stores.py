from pathlib import Path

import pytest

from villaz_cli.app_paths import LocalAppPaths
from villaz_cli.session_file_store import (
    JsonSessionStateStore,
)
from villaz_cli.session_lock import (
    JsonSessionLockStore,
)
from villaz_cli.session_stores import (
    EphemeralSessionStateStore,
    EphemeralSessionStateStoreError,
    LocalSessionStores,
    build_default_local_session_stores,
    build_local_session_stores,
)


def _paths(
    root: Path,
) -> LocalAppPaths:
    sessions_root = root / "sessions"

    return LocalAppPaths(
        state_root=root,
        sessions_root=sessions_root,
        session_state_root=sessions_root / "state",
        session_lock_root=sessions_root / "locks",
    )


def test_ephemeral_store_rejects_save() -> None:
    store = EphemeralSessionStateStore()

    with pytest.raises(
        EphemeralSessionStateStoreError,
        match="salvar estado persistente",
    ):
        store.save(
            session_id="session-001",
            state={},
        )


def test_ephemeral_store_rejects_load() -> None:
    store = EphemeralSessionStateStore()

    with pytest.raises(
        EphemeralSessionStateStoreError,
        match="carregar estado persistente",
    ):
        store.load(
            session_id="session-001",
        )


def test_ephemeral_store_rejects_list_session_ids() -> None:
    store = EphemeralSessionStateStore()

    with pytest.raises(
        EphemeralSessionStateStoreError,
        match="listar estado persistente",
    ):
        store.list_session_ids()


def test_ephemeral_store_rejects_purge() -> None:
    store = EphemeralSessionStateStore()

    with pytest.raises(
        EphemeralSessionStateStoreError,
        match="remover estado persistente",
    ):
        store.purge(
            session_id="session-001",
        )


def test_build_local_session_stores_uses_expected_concrete_types(
    tmp_path: Path,
) -> None:
    paths = _paths(
        tmp_path / "villaz-cli"
    )

    stores = build_local_session_stores(
        paths
    )

    assert isinstance(
        stores,
        LocalSessionStores,
    )
    assert isinstance(
        stores.state_store,
        JsonSessionStateStore,
    )
    assert isinstance(
        stores.lock_store,
        JsonSessionLockStore,
    )


def test_build_local_session_stores_wires_state_root(
    tmp_path: Path,
) -> None:
    paths = _paths(
        tmp_path / "villaz-cli"
    )

    stores = build_local_session_stores(
        paths
    )

    assert stores.state_store.root == (
        paths.session_state_root
    )


def test_build_local_session_stores_wires_lock_root(
    tmp_path: Path,
) -> None:
    paths = _paths(
        tmp_path / "villaz-cli"
    )

    stores = build_local_session_stores(
        paths
    )

    assert stores.lock_store.root == (
        paths.session_lock_root
    )


def test_build_local_session_stores_does_not_create_filesystem(
    tmp_path: Path,
) -> None:
    root = tmp_path / "not-created"
    paths = _paths(
        root
    )

    stores = build_local_session_stores(
        paths
    )

    assert isinstance(
        stores,
        LocalSessionStores,
    )
    assert not root.exists()


def test_default_builder_uses_default_paths(
    monkeypatch,
    tmp_path: Path,
) -> None:
    paths = _paths(
        tmp_path / "default-root"
    )

    monkeypatch.setattr(
        "villaz_cli.session_stores.get_default_local_app_paths",
        lambda: paths,
    )

    stores = build_default_local_session_stores()

    assert stores.state_store.root == (
        paths.session_state_root
    )
    assert stores.lock_store.root == (
        paths.session_lock_root
    )


def test_default_builder_does_not_create_filesystem(
    monkeypatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / "default-not-created"
    paths = _paths(
        root
    )

    monkeypatch.setattr(
        "villaz_cli.session_stores.get_default_local_app_paths",
        lambda: paths,
    )

    stores = build_default_local_session_stores()

    assert isinstance(
        stores,
        LocalSessionStores,
    )
    assert not root.exists()
