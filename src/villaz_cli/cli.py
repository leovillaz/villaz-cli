from importlib import metadata
from typing import Annotated

import typer


_DISTRIBUTION_NAME = "villaz-cli"
_HELP_TEXT = """Villaz-Lab CLI

Cliente interativo de terminal first-party para o Villaz-Lab Router.

Uso: villaz [opções]

Execute villaz sem argumentos para abrir o modo interativo.

Opções:
  --help     Exibe esta ajuda e encerra.
  --version  Exibe a versão e encerra.

Os comandos internos serão consultados futuramente por /help."""
_UNAVAILABLE_MESSAGE = (
    "O envio de prompts ao Router será implementado em um próximo bloco."
)


app = typer.Typer(
    add_completion=False,
    context_settings={"help_option_names": []},
    no_args_is_help=False,
)


def _installed_version() -> str:
    return metadata.version(_DISTRIBUTION_NAME)


def _show_help(value: bool) -> None:
    if value:
        typer.echo(_HELP_TEXT)
        raise typer.Exit(code=0)


def _show_version(value: bool) -> None:
    if value:
        typer.echo(f"Villaz-Lab CLI {_installed_version()}")
        raise typer.Exit(code=0)


def _interactive_shell() -> None:
    typer.echo(f"Villaz-Lab CLI {_installed_version()}")
    typer.echo(
        "Modo interativo de bootstrap — integração HTTP ainda não implementada."
    )
    typer.echo("Digite /exit para encerrar.")

    while True:
        typer.echo("> ", nl=False)
        try:
            line = input()
        except (EOFError, KeyboardInterrupt):
            typer.echo()
            return

        command = line.strip()
        if not command:
            continue
        if command == "/exit":
            return

        typer.echo(_UNAVAILABLE_MESSAGE)


@app.command()
def _entrypoint(
    help_: Annotated[
        bool,
        typer.Option(
            "--help",
            callback=_show_help,
            is_eager=True,
        ),
    ] = False,
    version_: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_show_version,
            is_eager=True,
        ),
    ] = False,
) -> None:
    _interactive_shell()


def main() -> None:
    app(prog_name="villaz")
