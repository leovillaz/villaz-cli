import time
from importlib import metadata
from typing import Annotated

import typer


from villaz_cli.http_client import (
    DEFAULT_ROUTER_URL,
    HealthResult,
    PromptResult,
    RouterAPIError,
    RouterClientError,
    RouterConnectionError,
    RouterProtocolError,
    get_health,
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
 /profile <id>   Seleciona um profile explícito.
 /profile auto   Retorna ao roteamento automático.
 /health         Verifica a saúde do Router.
 /status         Mostra endpoint, modo e saúde do Router.
 /profile <id>   Seleciona um profile explícito.
 /profile auto   Retorna ao roteamento automático.
 /exit           Encerra o Villaz-Lab CLI.
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


def _show_result(
    result: PromptResult,
    *,
    elapsed_seconds: float,
) -> None:
    typer.echo()
    typer.echo("[router]")
    typer.echo(f"estado:  {result.state}")
    typer.echo(f"profile: {result.profile}")
    typer.echo(f"modelo:  {result.model}")
    typer.echo(f"rota:    {result.route_id or '-'}")
    typer.echo(f"tempo:   {elapsed_seconds:.2f}s")
    typer.echo(f"tokens:  {result.output_tokens}")
    typer.echo(f"veloc.:  {result.tokens_per_second:.2f} tok/s")
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

def _show_health() -> None:
    health = get_health()

    typer.echo()
    typer.echo("[health]")
    typer.echo(f"live:  {health.live}")
    typer.echo(f"ready: {health.ready}")
    typer.echo()


def _show_status(explicit_profile: str | None) -> None:
    health = get_health()
    mode = explicit_profile if explicit_profile is not None else "auto"

    typer.echo()
    typer.echo("[status]")
    typer.echo(f"router: {DEFAULT_ROUTER_URL}")
    typer.echo(f"modo:   {mode}")
    typer.echo(f"live:   {health.live}")
    typer.echo(f"ready:  {health.ready}")
    typer.echo()

def _interactive_shell() -> None:
    explicit_profile: str | None = None

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

        if message == "/health":
            try:
                _show_health()
            except RouterConnectionError as exc:
                typer.echo()
                typer.echo(f"Erro: {exc}")
                typer.echo()
            except RouterProtocolError as exc:
                typer.echo()
                typer.echo(f"Erro: {exc}")
                typer.echo()

            continue

        if message == "/status":
            try:
                _show_status(explicit_profile)
            except RouterConnectionError as exc:
                typer.echo()
                typer.echo(f"Erro: {exc}")
                typer.echo()
            except RouterProtocolError as exc:
                typer.echo()
                typer.echo(f"Erro: {exc}")
                typer.echo()

            continue

        parts = message.split(maxsplit=1)

        if parts[0] == "/profile":
            if len(parts) == 1:
                typer.echo()
                typer.echo("Uso: /profile <id> ou /profile auto")
                typer.echo()
                continue

            requested_profile = parts[1]

            if requested_profile == "auto":
                explicit_profile = None
                typer.echo()
                typer.echo("Modo alterado para: auto")
                typer.echo()
                continue

            explicit_profile = requested_profile
            typer.echo()
            typer.echo(f"Profile ativo: {explicit_profile}")
            typer.echo()
            continue

        started_at = time.perf_counter()

        try:
            result = send_prompt(
                message,
                explicit_profile=explicit_profile,
            )
        except RouterAPIError as exc:
            _show_api_error(exc)
            continue
        except RouterClientError as exc:
            typer.echo()
            typer.echo(f"Falha ao acessar o Router: {exc}")
            typer.echo()
            continue
        elapsed_seconds = time.perf_counter() - started_at
        _show_result(result, elapsed_seconds=elapsed_seconds)


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
