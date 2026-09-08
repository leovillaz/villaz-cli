from importlib import metadata
from typing import Annotated

import typer

from villaz_cli.http_client import (
    PromptResult,
    RouterAPIError,
    RouterClientError,
    send_prompt,
)


_DISTRIBUTION_NAME = "villaz-cli"

_HELP_TEXT = """Villaz-Lab CLI

Cliente interativo de terminal first-party para o Villaz-Lab Router.

Uso: villaz [opções]

Execute villaz sem argumentos para abrir o modo interativo.

Opções:
--help     Exibe esta ajuda e encerra.
--version  Exibe a versão e encerra.

No modo interativo:
 /exit     Encerra o Villaz-Lab CLI.
"""

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


def _show_result(result: PromptResult) -> None:
    typer.echo()
    typer.echo("[router]")
    typer.echo(f"estado:  {result.state}")
    typer.echo(f"profile: {result.profile}")
    typer.echo(f"modelo:  {result.model}")
    typer.echo(f"rota:    {result.route_id or '-'}")
    typer.echo()
    typer.echo("[resposta]")
    typer.echo(result.response)
    typer.echo()


def _show_api_error(error: RouterAPIError) -> None:
    typer.echo()

    if error.code == "UNROUTED":
        typer.echo(
            "Não foi possível selecionar automaticamente um profile "
            "para esta solicitação."
        )
        typer.echo(
            "Tente reformular a mensagem com mais contexto sobre a tarefa."
        )
    elif error.code == "AMBIGUOUS":
        typer.echo(
            "A solicitação correspondeu a mais de um profile "
            "sem uma decisão determinística."
        )
    elif error.code == "INVALID_PROFILE":
        typer.echo("O Router rejeitou o profile informado.")
    else:
        typer.echo(f"Erro do Router [{error.code}]: {error.message}")

    typer.echo()


def _interactive_shell() -> None:
    typer.echo(f"Villaz-Lab CLI {_installed_version()}")
    typer.echo("Router: http://127.0.0.1:8000")
    typer.echo("Modo: auto")
    typer.echo("Digite /exit para encerrar.")

    while True:
        typer.echo("> ", nl=False)

        try:
            line = input()
        except (EOFError, KeyboardInterrupt):
            typer.echo()
            return

        message = line.strip()

        if not message:
            continue

        if message == "/exit":
            return

        try:
            result = send_prompt(message)
        except RouterAPIError as exc:
            _show_api_error(exc)
            continue
        except RouterClientError as exc:
            typer.echo()
            typer.echo(f"Falha ao acessar o Router: {exc}")
            typer.echo()
            continue

        _show_result(result)


@app.command()
def entrypoint(
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
