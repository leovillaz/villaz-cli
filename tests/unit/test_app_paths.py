from pathlib import Path

import pytest

from villaz_cli.app_paths import (
    AppPathError,
    LocalAppPaths,
    _resolve_local_app_paths,
)


def test_posix_uses_absolute_xdg_state_home() -> None:
    paths = _resolve_local_app_paths(
        os_name="posix",
        environ={
            "XDG_STATE_HOME": "/srv/user-state",
        },
        home=Path("/home/user"),
    )

    assert paths == LocalAppPaths(
        state_root=Path(
            "/srv/user-state/villaz-cli"
        ),
        sessions_root=Path(
            "/srv/user-state/villaz-cli/sessions"
        ),
        session_state_root=Path(
            "/srv/user-state/villaz-cli/sessions/state"
        ),
        session_lock_root=Path(
            "/srv/user-state/villaz-cli/sessions/locks"
        ),
    )


def test_posix_without_xdg_uses_home_fallback() -> None:
    paths = _resolve_local_app_paths(
        os_name="posix",
        environ={},
        home=Path("/home/user"),
    )

    assert paths.state_root == Path(
        "/home/user/.local/state/villaz-cli"
    )
    assert paths.sessions_root == Path(
        "/home/user/.local/state/villaz-cli/sessions"
    )
    assert paths.session_state_root == Path(
        "/home/user/.local/state/villaz-cli/sessions/state"
    )
    assert paths.session_lock_root == Path(
        "/home/user/.local/state/villaz-cli/sessions/locks"
    )


def test_empty_xdg_uses_home_fallback() -> None:
    paths = _resolve_local_app_paths(
        os_name="posix",
        environ={
            "XDG_STATE_HOME": "",
        },
        home=Path("/home/user"),
    )

    assert paths.state_root == Path(
        "/home/user/.local/state/villaz-cli"
    )


def test_relative_xdg_state_home_is_rejected() -> None:
    with pytest.raises(
        AppPathError,
        match="XDG_STATE_HOME",
    ):
        _resolve_local_app_paths(
            os_name="posix",
            environ={
                "XDG_STATE_HOME": "relative/state",
            },
            home=Path("/home/user"),
        )


def test_relative_home_is_rejected_for_posix_fallback() -> None:
    with pytest.raises(
        AppPathError,
        match="home",
    ):
        _resolve_local_app_paths(
            os_name="posix",
            environ={},
            home=Path("relative-home"),
        )


def test_other_non_windows_os_uses_posix_rule() -> None:
    paths = _resolve_local_app_paths(
        os_name="other",
        environ={
            "XDG_STATE_HOME": "/custom/state",
        },
        home=Path("/home/user"),
    )

    assert paths.state_root == Path(
        "/custom/state/villaz-cli"
    )


def test_windows_uses_localappdata() -> None:
    paths = _resolve_local_app_paths(
        os_name="nt",
        environ={
            "LOCALAPPDATA": r"C:\Users\Test\AppData\Local",
        },
        home=Path("/unused"),
    )

    assert str(
        paths.state_root
    ) == (
        r"C:\Users\Test\AppData\Local"
        r"\Villaz-Lab"
        r"\villaz-cli"
    )


def test_windows_sessions_structure_is_under_state_root() -> None:
    paths = _resolve_local_app_paths(
        os_name="nt",
        environ={
            "LOCALAPPDATA": r"C:\Users\Test\AppData\Local",
        },
        home=Path("/unused"),
    )

    state_root = str(
        paths.state_root
    )

    assert state_root.endswith(
        r"Villaz-Lab\villaz-cli"
    )


def test_windows_missing_localappdata_is_rejected() -> None:
    with pytest.raises(
        AppPathError,
        match="LOCALAPPDATA",
    ):
        _resolve_local_app_paths(
            os_name="nt",
            environ={},
            home=Path("/unused"),
        )


def test_windows_empty_localappdata_is_rejected() -> None:
    with pytest.raises(
        AppPathError,
        match="LOCALAPPDATA",
    ):
        _resolve_local_app_paths(
            os_name="nt",
            environ={
                "LOCALAPPDATA": "",
            },
            home=Path("/unused"),
        )


def test_windows_relative_localappdata_is_rejected() -> None:
    with pytest.raises(
        AppPathError,
        match="absoluto",
    ):
        _resolve_local_app_paths(
            os_name="nt",
            environ={
                "LOCALAPPDATA": r"AppData\Local",
            },
            home=Path("/unused"),
        )


def test_xdg_value_is_not_environment_expanded() -> None:
    with pytest.raises(
        AppPathError,
        match="XDG_STATE_HOME",
    ):
        _resolve_local_app_paths(
            os_name="posix",
            environ={
                "XDG_STATE_HOME": "$HOME/state",
                "HOME": "/home/user",
            },
            home=Path("/home/user"),
        )


def test_resolution_does_not_create_filesystem(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"

    paths = _resolve_local_app_paths(
        os_name="posix",
        environ={},
        home=home,
    )

    assert paths.state_root == (
        home
        / ".local"
        / "state"
        / "villaz-cli"
    )

    assert not home.exists()
