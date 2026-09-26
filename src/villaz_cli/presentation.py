from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.theme import Theme
from rich.text import Text


VILLAZ_THEME = Theme(
    {
        "villaz.primary": "cyan",
        "villaz.secondary": "magenta",
        "villaz.success": "green",
        "villaz.warning": "yellow",
        "villaz.error": "red",
        "villaz.muted": "dim",
    }
)


console = Console(
    theme=VILLAZ_THEME,
    highlight=False,
)


def show_help() -> None:
    options = Table.grid(padding=(0, 2))
    options.add_column(
        style="villaz.primary",
        no_wrap=True,
    )
    options.add_column()

    options.add_row(
        "--help",
        "Exibe esta ajuda e encerra.",
    )
    options.add_row(
        "--version",
        "Exibe a versão e encerra.",
    )

    controls = Table.grid(padding=(0, 2))
    controls.add_column(
        style="villaz.secondary",
        no_wrap=True,
    )
    controls.add_column()

    controls.add_row(
        "Enter",
        "Envia a mensagem.",
    )
    controls.add_row(
        "Shift+Enter",
        "Insere uma nova linha.",
    )
    controls.add_row(
        "F2",
        "Foca Sessões.",
    )
    controls.add_row(
        "F3",
        "Foca Conversa.",
    )
    controls.add_row(
        "F4",
        "Foca Contexto.",
    )
    controls.add_row(
        "F5",
        "Seleciona Profile.",
    )
    controls.add_row(
        "F6",
        "Foca Mensagem.",
    )
    controls.add_row(
        "Ctrl+Q",
        "Encerra o Villaz-Lab CLI.",
    )

    body = Table.grid(
        padding=(0, 0)
    )

    body.add_row(
        Text(
            "Cliente interativo de terminal first-party "
            "para o Villaz-Lab Router."
        )
    )
    body.add_row(
        Text("")
    )
    body.add_row(
        Text(
            "Uso: villaz [opções]",
            style="villaz.muted",
        )
    )
    body.add_row(
        Text(
            "Execute villaz sem argumentos para abrir "
            "a interface TUI full-screen."
        )
    )
    body.add_row(
        Text("")
    )
    body.add_row(
        Text(
            "Opções",
            style="villaz.muted",
        )
    )
    body.add_row(
        options
    )
    body.add_row(
        Text("")
    )
    body.add_row(
        Text(
            "Controles da TUI",
            style="villaz.muted",
        )
    )
    body.add_row(
        controls
    )
    body.add_row(
        Text("")
    )

    body.add_row(
        Text(
            "Profile",
            style="villaz.muted",
        )
    )

    body.add_row(
        Text(
            "F5 abre a seleção entre modo automático "
            "e profile explícito."
        )
    )

    body.add_row(
        Text(
            "A CLI não lista profiles; um ID explícito "
            "é validado pelo Router no envio."
        )
    )
    console.print(
        Panel(
            body,
            title="Villaz-Lab CLI",
            border_style="villaz.primary",
            expand=False,
        )
    )
