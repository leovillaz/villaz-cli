import importlib

import pytest

from typer.testing import CliRunner

from villaz_cli import cli
from villaz_cli.http_client import PromptResult, RouterAPIError


runner = CliRunner()
@pytest.fixture(autouse=True)
def healthy_router(monkeypatch) -> None:
    monkeypatch.setattr(
        cli,
        "get_health",
        lambda: cli.HealthResult(live="alive", ready="ready"),
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
    assert "/exit" in result.stdout
    assert "/profile <id>" in result.stdout
    assert "/profile auto" in result.stdout
    assert "/health" in result.stdout
    assert "/status" in result.stdout
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
    assert "Villaz-Lab CLI" in result.stdout
    assert "0.1.0" in result.stdout
    assert "Router" in result.stdout
    assert "http://127.0.0.1:8000" in result.stdout
    assert "● online" in result.stdout
    assert "Modo" in result.stdout
    assert "auto" in result.stdout
    assert "Digite uma mensagem ou /help" in result.stdout
    assert "villaz > " in result.stdout


def test_empty_line_is_silently_discarded(monkeypatch) -> None:
    def fail_if_called(message: str) -> PromptResult:
        raise AssertionError("linha vazia não deve acessar o Router")

    monkeypatch.setattr(cli, "send_prompt", fail_if_called)

    result = runner.invoke(cli.app, input="\n/exit\n")

    assert result.exit_code == 0


def test_regular_text_calls_router_and_displays_result(monkeypatch) -> None:
    received: list[str] = []

    def fake_send_prompt(
        message: str,
        *,
        explicit_profile: str | None = None,
    ) -> PromptResult:
        assert explicit_profile is None
        received.append(message)

        return PromptResult(
            response="VILLAZ-CLI-OK",
            profile="code-review-security",
            model="qwen2.5-coder:14b",
            state="routed",
            route_id="ROUTE-REVIEW-001",
            output_tokens=42,
            generation_duration_ns=1_500_000_000,
            tokens_per_second=28.0,
        )

    monkeypatch.setattr(cli, "send_prompt", fake_send_prompt)

    perf_counter_values = iter([100.0, 103.25])

    monkeypatch.setattr(
        cli.time,
        "perf_counter",
        lambda: next(perf_counter_values),
    )

    result = runner.invoke(
        cli.app,
        input="Faça uma revisão de segurança\n/exit\n",
    )

    assert result.exit_code == 0
    assert received == ["Faça uma revisão de segurança"]
    assert "Execução" in result.stdout
    assert "Estado" in result.stdout
    assert "routed" in result.stdout
    assert "Profile" in result.stdout
    assert "code-review-security" in result.stdout
    assert "Modelo" in result.stdout
    assert "qwen2.5-coder:14b" in result.stdout
    assert "Rota" in result.stdout
    assert "ROUTE-REVIEW-001" in result.stdout
    assert "[resposta]" in result.stdout
    assert "Tokens" in result.stdout
    assert "42" in result.stdout
    assert "Velocidade" in result.stdout
    assert "28.00 tok/s" in result.stdout
    assert "Tempo" in result.stdout
    assert "3.25s" in result.stdout
    assert "VILLAZ-CLI-OK" in result.stdout

def test_unrouted_is_presented_without_raw_json(monkeypatch) -> None:
    def fake_send_prompt(
        message: str,
        *,
        explicit_profile: str | None = None,
    ) -> PromptResult:
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
def test_profile_command_selects_explicit_profile(monkeypatch) -> None:
    calls: list[tuple[str, str | None]] = []

    def fake_send_prompt(
        message: str,
        *,
        explicit_profile: str | None = None,
    ) -> PromptResult:
        calls.append((message, explicit_profile))
        return PromptResult(
            response="OK",
            profile="code-review-security",
            model="qwen2.5-coder:14b",
            state="explicit",
            route_id=None,
            output_tokens=42,
            generation_duration_ns=1_500_000_000,
            tokens_per_second=28.0,
        )

    monkeypatch.setattr(cli, "send_prompt", fake_send_prompt)

    result = runner.invoke(
        cli.app,
        input=(
            "/profile code-review-security\n"
            "Teste\n"
            "/exit\n"
        ),
    )

    assert result.exit_code == 0
    assert "✓ Profile ativo: code-review-security" in result.stdout
    assert calls == [
        ("Teste", "code-review-security")
    ]
    assert "Estado" in result.stdout
    assert "explicit" in result.stdout
    assert "Rota" in result.stdout
    assert "-" in result.stdout


def test_profile_auto_returns_to_automatic_mode(monkeypatch) -> None:
    calls: list[tuple[str, str | None]] = []

    def fake_send_prompt(
        message: str,
        *,
        explicit_profile: str | None = None,
    ) -> PromptResult:
        calls.append((message, explicit_profile))
        return PromptResult(
            response="OK",
            profile="code-review-security",
            model="qwen2.5-coder:14b",
            state="routed",
            route_id="ROUTE-REVIEW-001",
            output_tokens=42,
            generation_duration_ns=1_500_000_000,
            tokens_per_second=28.0,
        )

    monkeypatch.setattr(cli, "send_prompt", fake_send_prompt)

    result = runner.invoke(
        cli.app,
        input=(
            "/profile code-review-security\n"
            "/profile auto\n"
            "Faça revisão de segurança\n"
            "/exit\n"
        ),
    )

    assert result.exit_code == 0
    assert "✓ Modo automático ativado." in result.stdout
    assert calls == [
        ("Faça revisão de segurança", None)
    ]


def test_profile_without_argument_shows_usage_without_calling_router(
    monkeypatch,
) -> None:
    def fail_if_called(
        message: str,
        *,
        explicit_profile: str | None = None,
    ) -> PromptResult:
        raise AssertionError(
            "/profile sem argumento não deve acessar o Router"
        )

    monkeypatch.setattr(cli, "send_prompt", fail_if_called)

    result = runner.invoke(
        cli.app,
        input="/profile\n/exit\n",
    )

    assert result.exit_code == 0
    assert "Uso: /profile <id> ou /profile auto" in result.stdout

def test_profiles_is_not_interpreted_as_profile_command(
    monkeypatch,
) -> None:
    received: list[str] = []

    def fake_send_prompt(
        message: str,
        *,
        explicit_profile: str | None = None,
    ) -> PromptResult:
        received.append(message)

        return PromptResult(
            response="OK",
            profile="code-review-security",
            model="qwen2.5-coder:14b",
            state="routed",
            route_id="ROUTE-REVIEW-001",
            output_tokens=42,
            generation_duration_ns=1_500_000_000,
            tokens_per_second=28.0,
        )

    monkeypatch.setattr(cli, "send_prompt", fake_send_prompt)

    result = runner.invoke(
        cli.app,
        input="/profiles\n/exit\n",
    )

    assert result.exit_code == 0
    assert received == ["/profiles"]

def test_health_command_displays_live_and_ready(monkeypatch) -> None:
    monkeypatch.setattr(
        cli,
        "get_health",
        lambda: cli.HealthResult(
            live="alive",
            ready="ready",
        ),
    )

    result = runner.invoke(
        cli.app,
        input="/health\n/exit\n",
    )

    assert result.exit_code == 0
    assert "Saúde do Router" in result.stdout
    assert "Live" in result.stdout
    assert "● online" in result.stdout
    assert "Ready" in result.stdout
    assert "✓ pronto" in result.stdout


def test_status_command_displays_auto_mode(monkeypatch) -> None:
    monkeypatch.setattr(
        cli,
        "get_health",
        lambda: cli.HealthResult(
            live="alive",
            ready="ready",
        ),
    )

    result = runner.invoke(
        cli.app,
        input="/status\n/exit\n",
    )

    assert result.exit_code == 0
    assert "Status" in result.stdout
    assert "Villaz-Lab Router" in result.stdout
    assert "Endpoint" in result.stdout
    assert "Router" in result.stdout
    assert "http://127.0.0.1:8000" in result.stdout
    assert "Modo" in result.stdout
    assert "auto" in result.stdout
    assert "Profile" in result.stdout
    assert "automático" in result.stdout
    assert "Live" in result.stdout
    assert "● online" in result.stdout
    assert "Ready" in result.stdout
    assert "✓ pronto" in result.stdout


def test_status_command_displays_explicit_profile(monkeypatch) -> None:
    monkeypatch.setattr(
        cli,
        "get_health",
        lambda: cli.HealthResult(
            live="alive",
            ready="ready",
        ),
    )

    result = runner.invoke(
        cli.app,
        input=(
            "/profile code-review-security\n"
            "/status\n"
            "/exit\n"
        ),
    )

    assert result.exit_code == 0
    assert "Modo" in result.stdout
    assert "explícito" in result.stdout
    assert "Profile" in result.stdout
    assert "code-review-security" in result.stdout


def test_startup_router_unavailable_does_not_end_shell(monkeypatch) -> None:
    monkeypatch.setattr(
        cli,
        "get_health",
        lambda: (_ for _ in ()).throw(cli.RouterConnectionError("offline")),
    )

    result = runner.invoke(cli.app, input="/exit\n")

    assert result.exit_code == 0
    assert "× indisponível" in result.stdout
    assert "villaz > " in result.stdout


def test_health_connection_error_keeps_shell_running(monkeypatch) -> None:
    calls = 0

    def fake_get_health() -> cli.HealthResult:
        nonlocal calls
        calls += 1
        if calls == 1:
            return cli.HealthResult(live="alive", ready="ready")
        raise cli.RouterConnectionError("offline")

    monkeypatch.setattr(cli, "get_health", fake_get_health)

    result = runner.invoke(cli.app, input="/health\n/exit\n")

    assert result.exit_code == 0
    assert "Erro do Router" in result.stdout
    assert "offline" in result.stdout
    assert result.stdout.count("villaz > ") >= 2


def test_status_protocol_error_keeps_shell_running(monkeypatch) -> None:
    calls = 0

    def fake_get_health() -> cli.HealthResult:
        nonlocal calls
        calls += 1
        if calls == 1:
            return cli.HealthResult(live="alive", ready="ready")
        raise cli.RouterProtocolError("invalid health response")

    monkeypatch.setattr(cli, "get_health", fake_get_health)

    result = runner.invoke(cli.app, input="/status\n/exit\n")

    assert result.exit_code == 0
    assert "Erro do Router" in result.stdout
    assert "invalid health response" in result.stdout
    assert result.stdout.count("villaz > ") >= 2


def test_prompt_client_error_keeps_shell_running(monkeypatch) -> None:
    monkeypatch.setattr(
        cli,
        "send_prompt",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            cli.RouterClientError("transport failure")
        ),
    )

    result = runner.invoke(cli.app, input="teste\n/exit\n")

    assert result.exit_code == 0
    assert "Falha ao acessar o Router" in result.stdout
    assert "transport failure" in result.stdout
    assert result.stdout.count("villaz > ") >= 2


def test_help_command_displays_help_without_calling_router(monkeypatch) -> None:
    def fail_if_called(
        message: str,
        *,
        explicit_profile: str | None = None,
    ) -> PromptResult:
        raise AssertionError("/help não deve enviar prompt ao Router")

    monkeypatch.setattr(cli, "send_prompt", fail_if_called)

    result = runner.invoke(
        cli.app,
        input="/help\n/exit\n",
    )

    assert result.exit_code == 0
    assert "Villaz-Lab CLI" in result.stdout
    assert "--help" in result.stdout
    assert "--version" in result.stdout
    assert "/profile <id>" in result.stdout
    assert "/profile auto" in result.stdout
    assert "/health" in result.stdout
    assert "/status" in result.stdout
    assert "/exit" in result.stdout
    assert result.stdout.count("villaz > ") >= 2
