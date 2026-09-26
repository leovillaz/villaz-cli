import builtins
import importlib
import sys
from contextlib import contextmanager

from typer.testing import CliRunner

from villaz_cli import cli

import pytest

runner = CliRunner()


class FakeStdin:
    def __init__(
        self,
        *,
        is_tty: bool = True,
        file_descriptor: int = 17,
    ) -> None:
        self._is_tty = is_tty
        self._file_descriptor = file_descriptor

    def isatty(self) -> bool:
        return self._is_tty

    def fileno(self) -> int:
        return self._file_descriptor


class FakeTermios:
    IXON = 0x0400
    TCSANOW = 0
    error = OSError

    def __init__(
        self,
        attributes: list,
    ) -> None:
        self.current_attributes = (
            attributes.copy()
        )
        self.set_calls: list[
            tuple[int, int, list]
        ] = []

    def tcgetattr(
        self,
        file_descriptor: int,
    ) -> list:
        assert file_descriptor == 17

        return (
            self.current_attributes.copy()
        )

    def tcsetattr(
        self,
        file_descriptor: int,
        when: int,
        attributes: list,
    ) -> None:
        assert file_descriptor == 17

        self.current_attributes = (
            attributes.copy()
        )

        self.set_calls.append(
            (
                file_descriptor,
                when,
                attributes.copy(),
            )
        )

def test_help_returns_static_text_without_starting_tui(
    monkeypatch,
) -> None:
    def fail_if_called() -> None:
        raise AssertionError(
            "a TUI não deve iniciar durante --help"
        )

    monkeypatch.setattr(
        cli,
        "_run_tui",
        fail_if_called,
    )

    result = runner.invoke(
        cli.app,
        ["--help"],
    )

    assert result.exit_code == 0
    assert "Villaz-Lab CLI" in result.stdout
    assert "--help" in result.stdout
    assert "--version" in result.stdout


def test_help_does_not_import_tui(
    monkeypatch,
) -> None:
    original_import = builtins.__import__

    def guarded_import(
        name,
        globals=None,
        locals=None,
        fromlist=(),
        level=0,
    ):
        if name.startswith("villaz_cli.tui"):
            raise AssertionError(
                "--help não deve importar a TUI"
            )

        return original_import(
            name,
            globals,
            locals,
            fromlist,
            level,
        )

    monkeypatch.setattr(
        builtins,
        "__import__",
        guarded_import,
    )

    result = runner.invoke(
        cli.app,
        ["--help"],
    )

    assert result.exit_code == 0


def test_version_returns_exactly_one_line_without_starting_tui(
    monkeypatch,
) -> None:
    def fail_if_called() -> None:
        raise AssertionError(
            "a TUI não deve iniciar durante --version"
        )

    monkeypatch.setattr(
        cli,
        "_run_tui",
        fail_if_called,
    )

    result = runner.invoke(
        cli.app,
        ["--version"],
    )

    assert result.exit_code == 0
    assert result.stdout == "Villaz-Lab CLI 0.1.0\n"


def test_version_does_not_import_tui(
    monkeypatch,
) -> None:
    original_import = builtins.__import__

    def guarded_import(
        name,
        globals=None,
        locals=None,
        fromlist=(),
        level=0,
    ):
        if name.startswith("villaz_cli.tui"):
            raise AssertionError(
                "--version não deve importar a TUI"
            )

        return original_import(
            name,
            globals,
            locals,
            fromlist,
            level,
        )

    monkeypatch.setattr(
        builtins,
        "__import__",
        guarded_import,
    )

    result = runner.invoke(
        cli.app,
        ["--version"],
    )

    assert result.exit_code == 0


def test_no_arguments_starts_tui_once(
    monkeypatch,
) -> None:
    calls = 0

    def fake_run_tui() -> None:
        nonlocal calls
        calls += 1

    monkeypatch.setattr(
        cli,
        "_run_tui",
        fake_run_tui,
    )

    result = runner.invoke(
        cli.app,
    )

    assert result.exit_code == 0
    assert calls == 1


def test_run_tui_instantiates_and_runs_villaz_app(
    monkeypatch,
) -> None:
    import villaz_cli.tui as tui

    calls: list[str] = []

    @contextmanager
    def fake_tty_guard():
        calls.append(
            "tty-enter"
        )

        try:
            yield
        finally:
            calls.append(
                "tty-exit"
            )

    class FakeVillazApp:
        def __init__(self) -> None:
            calls.append(
                "init"
            )

        def run(self) -> None:
            calls.append(
                "run"
            )

    monkeypatch.setattr(
        cli,
        "_tty_without_ixon",
        fake_tty_guard,
    )
    monkeypatch.setattr(
        tui,
        "VillazApp",
        FakeVillazApp,
    )

    cli._run_tui()

    assert calls == [
        "tty-enter",
        "init",
        "run",
        "tty-exit",
    ]


def test_main_uses_villaz_program_name(
    monkeypatch,
) -> None:
    received: dict[str, str] = {}

    def fake_app(
        *,
        prog_name: str,
    ) -> None:
        received["prog_name"] = prog_name

    monkeypatch.setattr(
        cli,
        "app",
        fake_app,
    )

    cli.main()

    assert received == {
        "prog_name": "villaz"
    }


def test_importing_package_has_no_output_or_operational_effects(
    capsys,
) -> None:
    import villaz_cli

    capsys.readouterr()

    importlib.reload(
        villaz_cli
    )

    captured = capsys.readouterr()

    assert captured.out == ""
    assert captured.err == ""


def test_tty_without_ixon_disables_and_restores_ixon(
    monkeypatch,
) -> None:
    original_attributes = [
        FakeTermios.IXON | 0x0020,
        0,
        0,
        0,
        0,
        0,
        [],
    ]

    fake_termios = FakeTermios(
        original_attributes
    )

    monkeypatch.setitem(
        sys.modules,
        "termios",
        fake_termios,
    )
    monkeypatch.setattr(
        cli.sys,
        "stdin",
        FakeStdin(),
    )

    with cli._tty_without_ixon():
        assert (
            fake_termios.current_attributes[0]
            & FakeTermios.IXON
        ) == 0

    assert (
        fake_termios.current_attributes
        == original_attributes
    )

    assert len(
        fake_termios.set_calls
    ) == 2


def test_tty_without_ixon_preserves_existing_disabled_state(
    monkeypatch,
) -> None:
    original_attributes = [
        0x0020,
        0,
        0,
        0,
        0,
        0,
        [],
    ]

    fake_termios = FakeTermios(
        original_attributes
    )

    monkeypatch.setitem(
        sys.modules,
        "termios",
        fake_termios,
    )
    monkeypatch.setattr(
        cli.sys,
        "stdin",
        FakeStdin(),
    )

    with cli._tty_without_ixon():
        pass

    assert (
        fake_termios.current_attributes
        == original_attributes
    )
    assert fake_termios.set_calls == []


def test_tty_without_ixon_restores_state_after_exception(
    monkeypatch,
) -> None:
    original_attributes = [
        FakeTermios.IXON | 0x0020,
        0,
        0,
        0,
        0,
        0,
        [],
    ]

    fake_termios = FakeTermios(
        original_attributes
    )

    monkeypatch.setitem(
        sys.modules,
        "termios",
        fake_termios,
    )
    monkeypatch.setattr(
        cli.sys,
        "stdin",
        FakeStdin(),
    )

    with pytest.raises(
        RuntimeError,
        match="falha simulada",
    ):
        with cli._tty_without_ixon():
            assert (
                fake_termios.current_attributes[0]
                & FakeTermios.IXON
            ) == 0

            raise RuntimeError(
                "falha simulada"
            )

    assert (
        fake_termios.current_attributes
        == original_attributes
    )


def test_tty_without_ixon_is_noop_without_tty(
    monkeypatch,
) -> None:
    original_import = builtins.__import__

    def guarded_import(
        name,
        globals=None,
        locals=None,
        fromlist=(),
        level=0,
    ):
        if name == "termios":
            raise AssertionError(
                "termios não deve ser importado "
                "sem TTY"
            )

        return original_import(
            name,
            globals,
            locals,
            fromlist,
            level,
        )

    monkeypatch.setattr(
        cli.sys,
        "stdin",
        FakeStdin(
            is_tty=False
        ),
    )
    monkeypatch.setattr(
        builtins,
        "__import__",
        guarded_import,
    )

    with cli._tty_without_ixon():
        pass


def test_tty_without_ixon_is_noop_when_termios_is_unavailable(
    monkeypatch,
) -> None:
    original_import = builtins.__import__

    def import_without_termios(
        name,
        globals=None,
        locals=None,
        fromlist=(),
        level=0,
    ):
        if name == "termios":
            raise ImportError(
                "termios indisponível"
            )

        return original_import(
            name,
            globals,
            locals,
            fromlist,
            level,
        )

    monkeypatch.setattr(
        cli.sys,
        "stdin",
        FakeStdin(),
    )
    monkeypatch.setattr(
        builtins,
        "__import__",
        import_without_termios,
    )

    with cli._tty_without_ixon():
        pass
