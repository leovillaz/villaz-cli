from contextlib import contextmanager
from collections.abc import Iterator

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


def show_confirmation(message: str) -> None:
    console.print(
        Text(f"✓ {message}", style="villaz.primary")
    )


def show_prompt() -> None:
    prompt = Text()
    prompt.append("villaz", style="villaz.primary")
    prompt.append(" ")
    prompt.append(">", style="villaz.secondary")
    prompt.append(" ")
    console.print(prompt, end="")


def show_execution(
    *,
    state: str,
    profile: str,
    model: str,
    route: str,
    elapsed_seconds: float,
    output_tokens: int,
    tokens_per_second: float,
) -> None:
    table = Table.grid(padding=(0, 1))
    table.add_column(style="villaz.muted", no_wrap=True)
    table.add_column()

    table.add_row("Estado", Text(state))
    table.add_row("Profile", Text(profile))
    table.add_row("Modelo", Text(model))
    table.add_row("Rota", Text(route))
    table.add_row("Tempo", Text(f"{elapsed_seconds:.2f}s"))
    table.add_row("Tokens", Text(str(output_tokens)))
    table.add_row("Velocidade", Text(f"{tokens_per_second:.2f} tok/s"))

    console.print(
        Panel(
            table,
            title="Execução",
            border_style="villaz.primary",
            expand=False,
        )
    )


@contextmanager
def waiting_for_response() -> Iterator[None]:
    if not console.is_terminal:
        yield
        return

    with console.status(
        Text("Aguardando resposta...", style="villaz.primary"),
        spinner="dots",
    ):
        yield


def show_health(*, live: str, ready: str) -> None:
    table = Table.grid(padding=(0, 1))
    table.add_column(style="villaz.muted", no_wrap=True)
    table.add_column()

    live_status = "● online" if live == "alive" else live
    ready_status = "✓ pronto" if ready == "ready" else ready

    table.add_row("Live", Text(live_status, style="villaz.success"))
    table.add_row("Ready", Text(ready_status, style="villaz.primary"))

    console.print(
        Panel(
            table,
            title="Saúde do Router",
            border_style="villaz.primary",
            expand=False,
        )
    )


def show_status(*, router: str, endpoint: str, mode: str, profile: str, live: str, ready: str) -> None:
    table = Table.grid(padding=(0, 1))
    table.add_column(style="villaz.muted", no_wrap=True)
    table.add_column()

    table.add_row("Router", Text(router))
    table.add_row("Endpoint", Text(endpoint))
    table.add_row("Modo", Text(mode))
    table.add_row("Profile", Text(profile))

    live_status = "● online" if live == "alive" else live
    ready_status = "✓ pronto" if ready == "ready" else ready

    table.add_row("Live", Text(live_status, style="villaz.success"))
    table.add_row("Ready", Text(ready_status, style="villaz.primary"))

    console.print(
        Panel(
            table,
            title="Status",
            border_style="villaz.primary",
            expand=False,
        )
    )


def show_splash(*, version: str, router: str, router_available: bool) -> None:
    status = Text()
    if router_available:
        status.append("● online", style="villaz.success")
    else:
        status.append("× indisponível", style="villaz.warning")

    table = Table.grid(padding=(0, 1))
    table.add_column(style="villaz.muted", no_wrap=True)
    table.add_column()

    table.add_row("Villaz-Lab CLI", Text(version, style="villaz.primary"))
    table.add_row("Router", Text(router))
    table.add_row("", status)
    table.add_row("Modo", Text("auto"))

    console.print(
        Panel(
            table,
            title="Villaz-Lab",
            subtitle="Interface local para o Villaz-Lab Router",
            border_style="villaz.primary",
            expand=False,
        )
    )
    console.print(Text("Digite uma mensagem ou /help", style="villaz.muted"))


def show_error(*, title: str, messages: tuple[str, ...], warning: bool = False) -> None:
    style = "villaz.warning" if warning else "villaz.error"
    symbol = "!" if warning else "×"

    body = Text()
    for index, message in enumerate(messages):
        if index:
            body.append("\n")
        body.append(f"{symbol} ", style=style)
        body.append(message)

    console.print(
        Panel(
            body,
            title=title,
            border_style=style,
            expand=False,
        )
    )


def show_help() -> None:
    options = Table.grid(padding=(0, 2))
    options.add_column(style="villaz.primary", no_wrap=True)
    options.add_column()
    options.add_row("--help", "Exibe esta ajuda e encerra.")
    options.add_row("--version", "Exibe a versão e encerra.")

    commands = Table.grid(padding=(0, 2))
    commands.add_column(style="villaz.secondary", no_wrap=True)
    commands.add_column()
    commands.add_row("/help", "Exibe esta ajuda.")
    commands.add_row("/profile <id>", "Seleciona um profile explícito.")
    commands.add_row("/profile auto", "Retorna ao roteamento automático.")
    commands.add_row("/health", "Verifica a saúde do Router.")
    commands.add_row("/status", "Mostra endpoint, modo e saúde do Router.")
    commands.add_row("/exit", "Encerra o Villaz-Lab CLI.")

    body = Table.grid(padding=(0, 0))
    body.add_row(Text("Cliente interativo de terminal first-party para o Villaz-Lab Router."))
    body.add_row(Text(""))
    body.add_row(Text("Uso: villaz [opções]", style="villaz.muted"))
    body.add_row(Text("Execute villaz sem argumentos para abrir o modo interativo."))
    body.add_row(Text(""))
    body.add_row(Text("Opções", style="villaz.muted"))
    body.add_row(options)
    body.add_row(Text(""))
    body.add_row(Text("No modo interativo", style="villaz.muted"))
    body.add_row(commands)

    console.print(
        Panel(
            body,
            title="Villaz-Lab CLI",
            border_style="villaz.primary",
            expand=False,
        )
    )
