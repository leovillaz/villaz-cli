import ntpath
import os
import posixpath
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


class AppPathError(Exception):
    """Raised when the local application state path cannot be resolved."""


@dataclass(frozen=True, slots=True)
class LocalAppPaths:
    state_root: Path
    sessions_root: Path
    session_state_root: Path
    session_lock_root: Path


def _build_paths(
    state_root: Path,
) -> LocalAppPaths:
    sessions_root = state_root / "sessions"

    return LocalAppPaths(
        state_root=state_root,
        sessions_root=sessions_root,
        session_state_root=sessions_root / "state",
        session_lock_root=sessions_root / "locks",
    )


def _resolve_local_app_paths(
    *,
    os_name: str,
    environ: Mapping[str, str],
    home: Path,
) -> LocalAppPaths:
    if os_name == "nt":
        local_app_data = environ.get(
            "LOCALAPPDATA",
            "",
        )

        if not local_app_data:
            raise AppPathError(
                "LOCALAPPDATA não está definido."
            )

        if not ntpath.isabs(
            local_app_data
        ):
            raise AppPathError(
                "LOCALAPPDATA deve ser um caminho absoluto."
            )

        state_root = Path(
            ntpath.join(
                local_app_data,
                "Villaz-Lab",
                "villaz-cli",
            )
        )

        return _build_paths(
            state_root
        )

    xdg_state_home = environ.get(
        "XDG_STATE_HOME",
        "",
    )

    if xdg_state_home:
        if not posixpath.isabs(
            xdg_state_home
        ):
            raise AppPathError(
                "XDG_STATE_HOME deve ser um caminho absoluto."
            )

        state_root = Path(
            xdg_state_home
        ) / "villaz-cli"

        return _build_paths(
            state_root
        )

    if not home.is_absolute():
        raise AppPathError(
            "O diretório home deve ser um caminho absoluto."
        )

    state_root = (
        home
        / ".local"
        / "state"
        / "villaz-cli"
    )

    return _build_paths(
        state_root
    )


def get_default_local_app_paths() -> LocalAppPaths:
    return _resolve_local_app_paths(
        os_name=os.name,
        environ=os.environ,
        home=Path.home(),
    )
