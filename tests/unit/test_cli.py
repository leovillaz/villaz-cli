import importlib

from typer.testing import CliRunner

from villaz_cli import cli
from villaz_cli.http_client import PromptResult, RouterAPIError


runner = CliRunner()


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
    assert "/exit" in result.stdout
    assert "Router:" not in result.stdout
    assert "install-completion" not in result.stdout
    assert "show-completion" not in result.stdout


def test_version_returns_exactly_one_line_without_starting_shell(
    monkeypatch,
) -> None:
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
    assert "Router: http://127.0.0.1:8000" in result.stdout
    assert "Modo: auto" in result.stdout
    assert "> " in result.stdout


def test_empty_line_is_silently_discarded(monkeypatch) -> None:
    def fail_if_called(message: str) -> PromptResult:
        raise AssertionError("linha vazia não deve acessar o Router")

    monkeypatch.setattr(cli, "send_prompt", fail_if_called)

    result = runner.invoke(cli.app, input="\n/exit\n")

    assert result.exit_code == 0


def test_regular_text_calls_router_and_displays_result(monkeypatch) -> None:
    received: list[str] = []

    def fake_send_prompt(message: str) -> PromptResult:
        received.append(message)
        return PromptResult(
            response="VILLAZ-CLI-OK",
            profile="code-review-security",
            model="qwen2.5-coder:14b",
            state="routed",
            route_id="ROUTE-REVIEW-001",
        )

    monkeypatch.setattr(cli, "send_prompt", fake_send_prompt)

    result = runner.invoke(
        cli.app,
        input="Faça uma revisão de segurança\n/exit\n",
    )

    assert result.exit_code == 0
    assert received == ["Faça uma revisão de segurança"]
    assert "[router]" in result.stdout
    assert "estado:  routed" in result.stdout
    assert "profile: code-review-security" in result.stdout
    assert "modelo:  qwen2.5-coder:14b" in result.stdout
    assert "rota:    ROUTE-REVIEW-001" in result.stdout
    assert "[resposta]" in result.stdout
    assert "VILLAZ-CLI-OK" in result.stdout


def test_unrouted_is_presented_without_raw_json(monkeypatch) -> None:
    def fake_send_prompt(message: str) -> PromptResult:
        raise RouterAPIError(
            code="UNROUTED",
            message="The request could not be routed.",
        )

    monkeypatch.setattr(cli, "send_prompt", fake_send_prompt)

    result = runner.invoke(cli.app, input="Olá\n/exit\n")

    assert result.exit_code == 0
    assert "Não foi possível selecionar automaticamente" in result.stdout
    assert '"error"' not in result.stdout
    assert "Traceback" not in result.stdout


def test_eof_finishes_without_traceback() -> None:
    result = runner.invoke(cli.app, input="")

    assert result.exit_code == 0
    assert "Traceback" not in result.stdout
    assert result.exception is None


def test_importing_package_has_no_output_or_operational_effects(
    capsys,
) -> None:
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
