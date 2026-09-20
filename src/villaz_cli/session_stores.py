from dataclasses import dataclass
from typing import Any

from villaz_cli.app_paths import (
    LocalAppPaths,
    get_default_local_app_paths,
)
from villaz_cli.session_file_store import (
    JsonSessionStateStore,
)
from villaz_cli.session_lock import (
    JsonSessionLockStore,
)


class EphemeralSessionStateStoreError(RuntimeError):
    """Raised when an ephemeral flow attempts to access persistence."""


class EphemeralSessionStateStore:
    """Fail-fast sentinel store for ephemeral session flows."""

    def save(
        self,
        *,
        session_id: str,
        state: dict[str, Any],
    ) -> None:
        raise EphemeralSessionStateStoreError(
            "Uma Session EPHEMERAL não pode salvar estado persistente."
        )

    def load(
        self,
        *,
        session_id: str,
    ) -> dict[str, Any]:
        raise EphemeralSessionStateStoreError(
            "Uma Session EPHEMERAL não pode carregar estado persistente."
        )

    def list_session_ids(self) -> tuple[str, ...]:
        raise EphemeralSessionStateStoreError(
            "Uma Session EPHEMERAL não pode listar estado persistente."
        )

    def purge(
        self,
        *,
        session_id: str,
    ) -> None:
        raise EphemeralSessionStateStoreError(
            "Uma Session EPHEMERAL não pode remover estado persistente."
        )


@dataclass(frozen=True, slots=True)
class LocalSessionStores:
    state_store: JsonSessionStateStore
    lock_store: JsonSessionLockStore


def build_local_session_stores(
    paths: LocalAppPaths,
) -> LocalSessionStores:
    return LocalSessionStores(
        state_store=JsonSessionStateStore(
            paths.session_state_root
        ),
        lock_store=JsonSessionLockStore(
            paths.session_lock_root
        ),
    )


def build_default_local_session_stores() -> LocalSessionStores:
    return build_local_session_stores(
        get_default_local_app_paths()
    )
