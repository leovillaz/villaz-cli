import importlib

from typer.testing import CliRunner

from villaz_cli import cli


runner = CliRunner()
UNAVAILABLE_MESSAGE = (
    "O envio de prompts ao Router será implementado em um próximo bloco."
)


def test_help_returns_static_text_without_starting_shell(monkeypatch) -> None:
    def fail_if_called() -> None:
        raise AssertionError("a shell não deve iniciar durante --help")

    monkeypatch.setattr(cli, "_interactive_shell", fail_if_called)

    result = runner.invoke(cli.app, ["--help"])

    assert result.exit_code == 0
    assert "Villaz-Lab CLI" in result.stdout
    assert "Cliente interativo de terminal first-party" in result.stdout
    assert "Uso: villaz [opções]" in result.stdout
    assert "villaz sem argumentos" in result.stdout
    assert "--help" in result.stdout
    assert "--version" in result.stdout
    assert "/help" in result.stdout
    assert "Modo interativo de bootstrap" not in result.stdout
    assert "install-completion" not in result.stdout
    assert "show-completion" not in result.stdout


def test_version_returns_exactly_one_line_without_starting_shell(monkeypatch) -> None:
    def fail_if_called() -> None:
        raise AssertionError("a shell não deve iniciar durante --version")

    monkeypatch.setattr(cli, "_interactive_shell", fail_if_called)

    result = runner.invoke(cli.app, ["--version"])

    assert result.exit_code == 0
    assert result.stdout == "Villaz-Lab CLI 0.1.0\n"


def test_no_arguments_starts_shell_and_exit_finishes_normally() -> None:
    result = runner.invoke(cli.app, input="/exit\n")

    assert result.exit_code == 0
    assert "Villaz-Lab CLI 0.1.0" in result.stdout
    assert "Modo interativo de bootstrap" in result.stdout
    assert "Digite /exit para encerrar." in result.stdout
    assert "> " in result.stdout
    assert UNAVAILABLE_MESSAGE not in result.stdout


def test_empty_line_is_silently_discarded() -> None:
    result = runner.invoke(cli.app, input="\n/exit\n")

    assert result.exit_code == 0
    assert UNAVAILABLE_MESSAGE not in result.stdout


def test_regular_text_shows_unavailable_message_and_returns_to_prompt() -> None:
    result = runner.invoke(cli.app, input="Olá\n/exit\n")

    assert result.exit_code == 0
    assert result.stdout.count(UNAVAILABLE_MESSAGE) == 1
    assert result.stdout.count("> ") >= 2


def test_eof_finishes_without_traceback() -> None:
    result = runner.invoke(cli.app, input="")

    assert result.exit_code == 0
    assert "Traceback" not in result.stdout
    assert result.exception is None


def test_importing_package_has_no_output_or_operational_effects(capsys) -> None:
    import villaz_cli

    capsys.readouterr()
    importlib.reload(villaz_cli)
    captured = capsys.readouterr()

    assert captured.out == ""
    assert captured.err == ""

def test_keyboard_interrupt_finishes_without_traceback(monkeypatch) -> None:
    def raise_keyboard_interrupt() -> str:
        raise KeyboardInterrupt

    monkeypatch.setattr("builtins.input", raise_keyboard_interrupt)

    result = runner.invoke(cli.app)

    assert result.exit_code == 0
    assert "Traceback" not in result.stdout
    assert result.exception is None
