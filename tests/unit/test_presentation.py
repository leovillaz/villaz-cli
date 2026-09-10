from io import StringIO

from rich.console import Console

from villaz_cli import presentation
from villaz_cli.presentation import VILLAZ_THEME


def test_theme_defines_approved_semantic_styles_without_background() -> None:
    expected_styles = {
        "villaz.primary",
        "villaz.secondary",
        "villaz.success",
        "villaz.warning",
        "villaz.error",
        "villaz.muted",
    }

    assert expected_styles <= VILLAZ_THEME.styles.keys()

    for style_name in expected_styles:
        assert VILLAZ_THEME.styles[style_name].bgcolor is None


def test_theme_remains_legible_when_color_is_disabled() -> None:
    output = StringIO()
    test_console = Console(
        file=output,
        theme=VILLAZ_THEME,
        color_system=None,
        highlight=False,
    )

    test_console.print("Villaz-Lab CLI", style="villaz.primary")

    assert output.getvalue() == "Villaz-Lab CLI\n"


def test_show_confirmation_preserves_literal_message_without_color(
    monkeypatch,
) -> None:
    output = StringIO()
    test_console = Console(
        file=output,
        theme=VILLAZ_THEME,
        color_system=None,
        highlight=False,
    )

    monkeypatch.setattr(presentation, "console", test_console)

    presentation.show_confirmation("Profile ativo: [review]")

    assert output.getvalue() == "✓ Profile ativo: [review]\n"


def test_show_prompt_remains_legible_without_color(monkeypatch) -> None:
    output = StringIO()
    test_console = Console(
        file=output,
        theme=VILLAZ_THEME,
        color_system=None,
        highlight=False,
    )

    monkeypatch.setattr(presentation, "console", test_console)

    presentation.show_prompt()

    assert output.getvalue() == "villaz > "


def test_show_execution_displays_all_fields_without_color(monkeypatch) -> None:
    output = StringIO()
    test_console = Console(
        file=output,
        theme=VILLAZ_THEME,
        color_system=None,
        highlight=False,
        width=120,
    )

    monkeypatch.setattr(presentation, "console", test_console)

    presentation.show_execution(
        state="routed",
        profile="code-review-security",
        model="qwen2.5-coder:14b",
        route="ROUTE-REVIEW-001",
        elapsed_seconds=3.25,
        output_tokens=42,
        tokens_per_second=28.0,
    )

    rendered = output.getvalue()

    assert "Execução" in rendered
    assert "Estado" in rendered
    assert "routed" in rendered
    assert "Profile" in rendered
    assert "code-review-security" in rendered
    assert "Modelo" in rendered
    assert "qwen2.5-coder:14b" in rendered
    assert "Rota" in rendered
    assert "ROUTE-REVIEW-001" in rendered
    assert "Tempo" in rendered
    assert "3.25s" in rendered
    assert "Tokens" in rendered
    assert "42" in rendered
    assert "Velocidade" in rendered
    assert "28.00 tok/s" in rendered


def test_waiting_for_response_is_silent_when_output_is_not_terminal(
    monkeypatch,
) -> None:
    output = StringIO()
    test_console = Console(
        file=output,
        theme=VILLAZ_THEME,
        color_system=None,
        highlight=False,
    )

    monkeypatch.setattr(presentation, "console", test_console)

    executed = False

    with presentation.waiting_for_response():
        executed = True

    assert executed is True
    assert output.getvalue() == ""


def test_show_health_renders_live_and_ready(monkeypatch) -> None:
    output = StringIO()
    test_console = Console(
        file=output,
        theme=VILLAZ_THEME,
        color_system=None,
        highlight=False,
        width=80,
    )

    monkeypatch.setattr(presentation, "console", test_console)

    presentation.show_health(
        live="alive",
        ready="ready",
    )

    rendered = output.getvalue()
    assert "Saúde do Router" in rendered
    assert "Live" in rendered
    assert "● online" in rendered
    assert "Ready" in rendered
    assert "✓ pronto" in rendered


def test_show_status_renders_router_mode_and_health(monkeypatch) -> None:
    output = StringIO()
    test_console = Console(
        file=output,
        theme=VILLAZ_THEME,
        color_system=None,
        highlight=False,
        width=100,
    )

    monkeypatch.setattr(presentation, "console", test_console)

    presentation.show_status(
        router="Villaz-Lab Router",
        endpoint="http://127.0.0.1:8000",
        mode="auto",
        profile="automático",
        live="alive",
        ready="ready",
    )

    rendered = output.getvalue()
    assert "Status" in rendered
    assert "Router" in rendered
    assert "http://127.0.0.1:8000" in rendered
    assert "Modo" in rendered
    assert "auto" in rendered
    assert "Profile" in rendered
    assert "automático" in rendered
    assert "Live" in rendered
    assert "● online" in rendered
    assert "Ready" in rendered
    assert "✓ pronto" in rendered


def test_show_splash_renders_online_state(monkeypatch) -> None:
    output = StringIO()
    test_console = Console(
        file=output,
        theme=VILLAZ_THEME,
        color_system=None,
        highlight=False,
        width=120,
    )

    monkeypatch.setattr(presentation, "console", test_console)

    presentation.show_splash(
        version="0.1.0",
        router="http://127.0.0.1:8000",
        router_available=True,
    )

    rendered = output.getvalue()
    assert "Villaz-Lab CLI" in rendered
    assert "0.1.0" in rendered
    assert "http://127.0.0.1:8000" in rendered
    assert "● online" in rendered
    assert "Modo" in rendered
    assert "auto" in rendered
    assert "Digite uma mensagem ou /help" in rendered


def test_show_splash_renders_unavailable_state(monkeypatch) -> None:
    output = StringIO()
    test_console = Console(
        file=output,
        theme=VILLAZ_THEME,
        color_system=None,
        highlight=False,
        width=120,
    )

    monkeypatch.setattr(presentation, "console", test_console)

    presentation.show_splash(
        version="0.1.0",
        router="http://127.0.0.1:8000",
        router_available=False,
    )

    assert "× indisponível" in output.getvalue()


def test_show_error_renders_warning_and_error(monkeypatch) -> None:
    output = StringIO()
    test_console = Console(
        file=output,
        theme=VILLAZ_THEME,
        color_system=None,
        highlight=False,
        width=120,
    )

    monkeypatch.setattr(presentation, "console", test_console)

    presentation.show_error(
        title="Roteamento",
        messages=("Mensagem de aviso.",),
        warning=True,
    )
    presentation.show_error(
        title="Erro do Router",
        messages=("Mensagem de erro.",),
    )

    rendered = output.getvalue()
    assert "Roteamento" in rendered
    assert "! Mensagem de aviso." in rendered
    assert "Erro do Router" in rendered
    assert "× Mensagem de erro." in rendered


def test_show_execution_preserves_values_in_narrow_terminal(monkeypatch) -> None:
    output = StringIO()
    test_console = Console(
        file=output,
        theme=VILLAZ_THEME,
        color_system=None,
        highlight=False,
        width=40,
    )

    monkeypatch.setattr(presentation, "console", test_console)

    presentation.show_execution(
        state="routed",
        profile="code-review-security",
        model="qwen2.5-coder:14b",
        route="ROUTE-REVIEW-001",
        elapsed_seconds=3.25,
        output_tokens=42,
        tokens_per_second=28.0,
    )

    rendered = output.getvalue()
    compact = rendered.replace("\n", "")

    assert "code-review-security" in compact
    assert "qwen2.5-coder:14b" in compact
    assert "ROUTE-REVIEW-001" in compact


def test_show_status_preserves_endpoint_in_narrow_terminal(monkeypatch) -> None:
    output = StringIO()
    test_console = Console(
        file=output,
        theme=VILLAZ_THEME,
        color_system=None,
        highlight=False,
        width=40,
    )

    monkeypatch.setattr(presentation, "console", test_console)

    presentation.show_status(
        router="Villaz-Lab Router",
        endpoint="http://127.0.0.1:8000",
        mode="explícito",
        profile="code-review-security",
        live="alive",
        ready="ready",
    )

    rendered = output.getvalue()
    compact = rendered.replace("\n", "")

    assert "http://127.0.0.1:8000" in compact
    assert "code-review-security" in compact
    assert "● online" in compact
    assert "✓ pronto" in compact


def test_show_splash_preserves_core_values_in_narrow_terminal(monkeypatch) -> None:
    output = StringIO()
    test_console = Console(
        file=output,
        theme=VILLAZ_THEME,
        color_system=None,
        highlight=False,
        width=40,
    )

    monkeypatch.setattr(presentation, "console", test_console)

    presentation.show_splash(
        version="0.1.0",
        router="http://127.0.0.1:8000",
        router_available=True,
    )

    rendered = output.getvalue()
    compact = rendered.replace("\n", "")

    assert "0.1.0" in compact
    assert "http://127.0.0.1:8000" in compact
    assert "● online" in compact
    assert "auto" in compact
    assert "Digite uma mensagem ou /help" in compact


def test_show_health_preserves_states_in_narrow_terminal(monkeypatch) -> None:
    output = StringIO()
    test_console = Console(
        file=output,
        theme=VILLAZ_THEME,
        color_system=None,
        highlight=False,
        width=40,
    )

    monkeypatch.setattr(presentation, "console", test_console)

    presentation.show_health(
        live="alive",
        ready="ready",
    )

    rendered = output.getvalue()
    assert "Live" in rendered
    assert "● online" in rendered
    assert "Ready" in rendered
    assert "✓ pronto" in rendered


def test_show_error_preserves_message_in_narrow_terminal(monkeypatch) -> None:
    output = StringIO()
    test_console = Console(
        file=output,
        theme=VILLAZ_THEME,
        color_system=None,
        highlight=False,
        width=40,
    )

    monkeypatch.setattr(presentation, "console", test_console)

    presentation.show_error(
        title="Erro do Router",
        messages=(
            "Falha ao acessar o Router devido a uma resposta de protocolo inválida.",
        ),
    )

    rendered = output.getvalue()
    compact = rendered.replace("\n", "")

    assert "Erro do Router" in compact
    assert "Falha ao acessar o Router devido a" in rendered
    assert "uma resposta de protocolo inválida." in rendered


def test_show_help_renders_current_commands_without_color(monkeypatch) -> None:
    output = StringIO()
    test_console = Console(
        file=output,
        theme=VILLAZ_THEME,
        color_system=None,
        highlight=False,
        width=80,
    )

    monkeypatch.setattr(presentation, "console", test_console)

    presentation.show_help()

    rendered = output.getvalue()

    assert "Villaz-Lab CLI" in rendered
    assert "/help" in rendered
    assert "Uso: villaz [opções]" in rendered
    assert "--help" in rendered
    assert "--version" in rendered
    assert "/profile <id>" in rendered
    assert "/profile auto" in rendered
    assert "/health" in rendered
    assert "/status" in rendered
    assert "/exit" in rendered
    assert "/profiles" not in rendered
    assert "/retry" not in rendered
    assert "/last" not in rendered
    assert "/clear" not in rendered
    assert "/about" not in rendered


def test_show_help_preserves_commands_in_narrow_terminal(monkeypatch) -> None:
    output = StringIO()
    test_console = Console(
        file=output,
        theme=VILLAZ_THEME,
        color_system=None,
        highlight=False,
        width=40,
    )

    monkeypatch.setattr(presentation, "console", test_console)

    presentation.show_help()

    rendered = output.getvalue()

    assert "/profile <id>" in rendered
    assert "/profile auto" in rendered
    assert "/health" in rendered
    assert "/status" in rendered
    assert "/exit" in rendered
    assert "--help" in rendered
    assert "--version" in rendered
