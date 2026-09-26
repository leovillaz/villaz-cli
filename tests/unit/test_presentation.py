from io import StringIO

from rich.console import Console

from villaz_cli import presentation
from villaz_cli.presentation import VILLAZ_THEME


def _test_console(
    *,
    output: StringIO,
    width: int = 80,
) -> Console:
    return Console(
        file=output,
        theme=VILLAZ_THEME,
        color_system=None,
        highlight=False,
        width=width,
    )


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
        assert (
            VILLAZ_THEME.styles[
                style_name
            ].bgcolor
            is None
        )


def test_theme_remains_legible_when_color_is_disabled() -> None:
    output = StringIO()

    console = _test_console(
        output=output,
    )

    console.print(
        "Villaz-Lab CLI",
        style="villaz.primary",
    )

    assert (
        output.getvalue()
        == "Villaz-Lab CLI\n"
    )


def test_show_help_renders_external_options_and_tui_controls(
    monkeypatch,
) -> None:
    output = StringIO()

    console = _test_console(
        output=output,
    )

    monkeypatch.setattr(
        presentation,
        "console",
        console,
    )

    presentation.show_help()

    rendered = output.getvalue()

    assert "Villaz-Lab CLI" in rendered
    assert (
        "Cliente interativo de terminal first-party"
        in rendered
    )
    assert "Uso: villaz [opções]" in rendered
    assert "interface TUI full-screen" in rendered

    assert "--help" in rendered
    assert "--version" in rendered

    assert "Controles da TUI" in rendered
    assert "Enter" in rendered
    assert "Shift+Enter" in rendered
    assert "F2" in rendered
    assert "F3" in rendered
    assert "F4" in rendered
    assert "F5" in rendered
    assert "F6" in rendered
    assert "modo automático" in rendered
    assert "profile explícito" in rendered
    assert "não lista profiles" in rendered
    assert "validado pelo Router" in rendered
    assert "Ctrl+Q" in rendered


def test_show_help_does_not_advertise_unimplemented_slash_commands(
    monkeypatch,
) -> None:
    output = StringIO()

    console = _test_console(
        output=output,
    )

    monkeypatch.setattr(
        presentation,
        "console",
        console,
    )

    presentation.show_help()

    rendered = output.getvalue()

    assert "/help" not in rendered
    assert "/profile" not in rendered
    assert "/health" not in rendered
    assert "/status" not in rendered
    assert "/exit" not in rendered
    assert "/profiles" not in rendered
    assert "/retry" not in rendered
    assert "/last" not in rendered
    assert "/clear" not in rendered
    assert "/about" not in rendered


def test_show_help_preserves_tui_controls_in_narrow_terminal(
    monkeypatch,
) -> None:
    output = StringIO()

    console = _test_console(
        output=output,
        width=40,
    )

    monkeypatch.setattr(
        presentation,
        "console",
        console,
    )

    presentation.show_help()

    rendered = output.getvalue()
    compact = rendered.replace(
        "\n",
        "",
    )

    assert "--help" in compact
    assert "--version" in compact
    assert "Shift+Enter" in compact
    assert "F2" in compact
    assert "F3" in compact
    assert "F4" in compact
    assert "F5" in compact
    assert "F6" in compact
    assert "Ctrl+Q" in compact
