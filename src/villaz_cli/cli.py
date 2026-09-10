import time
from importlib import metadata
from typing import Annotated

import typer


from villaz_cli.presentation import show_confirmation, show_error, show_execution, show_health, show_help, show_prompt, show_splash, show_status, waiting_for_response
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


app = typer.Typer(
    add_completion=False,
    context_settings={"help_option_names": []},
    no_args_is_help=False,
)


def _installed_version() -> str:
    return metadata.version(_DISTRIBUTION_NAME)


def _show_help(value: bool) -> None:
    if value:
        show_help()
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
    show_execution(
        state=result.state,
        profile=result.profile,
        model=result.model,
        route=result.route_id or "-",
        elapsed_seconds=elapsed_seconds,
        output_tokens=result.output_tokens,
        tokens_per_second=result.tokens_per_second,
    )
    typer.echo()
    typer.echo("[resposta]")
    typer.echo(result.response)
    typer.echo()


def _show_api_error(error: RouterAPIError) -> None:
    typer.echo()

    if error.code == "UNROUTED":
        show_error(
            title="Roteamento",
            messages=(
                "Não foi possível selecionar automaticamente um profile para esta solicitação.",
                "Tente reformular a mensagem com mais contexto sobre a tarefa.",
            ),
            warning=True,
        )
    elif error.code == "AMBIGUOUS":
        show_error(
            title="Roteamento",
            messages=(
                "A solicitação correspondeu a mais de um profile sem uma decisão determinística.",
            ),
            warning=True,
        )
    elif error.code == "INVALID_PROFILE":
        show_error(
            title="Erro do Router",
            messages=("O Router rejeitou o profile informado.",),
        )
    else:
        show_error(
            title=f"Erro do Router [{error.code}]",
            messages=(error.message,),
        )

    typer.echo()


def _show_health() -> None:
    health = get_health()

    typer.echo()
    show_health(
        live=health.live,
        ready=health.ready,
    )
    typer.echo()


def _show_status(explicit_profile: str | None) -> None:
    health = get_health()
    mode = "explícito" if explicit_profile is not None else "auto"
    profile = explicit_profile if explicit_profile is not None else "automático"

    typer.echo()
    show_status(
        router="Villaz-Lab Router",
        endpoint=DEFAULT_ROUTER_URL,
        mode=mode,
        profile=profile,
        live=health.live,
        ready=health.ready,
    )
    typer.echo()

def _interactive_shell() -> None:
    explicit_profile: str | None = None

    try:
        get_health()
        router_available = True
    except (RouterConnectionError, RouterProtocolError):
        router_available = False

    show_splash(
        version=_installed_version(),
        router=DEFAULT_ROUTER_URL,
        router_available=router_available,
    )
    typer.echo()

    while True:
        show_prompt()

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

        if message == "/help":
            typer.echo()
            show_help()
            typer.echo()
            continue

        if message == "/health":
            try:
                _show_health()
            except RouterConnectionError as exc:
                typer.echo()
                show_error(title="Erro do Router", messages=(str(exc),))
                typer.echo()
            except RouterProtocolError as exc:
                typer.echo()
                show_error(title="Erro do Router", messages=(str(exc),))
                typer.echo()

            continue

        if message == "/status":
            try:
                _show_status(explicit_profile)
            except RouterConnectionError as exc:
                typer.echo()
                show_error(title="Erro do Router", messages=(str(exc),))
                typer.echo()
            except RouterProtocolError as exc:
                typer.echo()
                show_error(title="Erro do Router", messages=(str(exc),))
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
                show_confirmation("Modo automático ativado.")
                typer.echo()
                continue

            explicit_profile = requested_profile
            typer.echo()
            show_confirmation(f"Profile ativo: {explicit_profile}")
            typer.echo()
            continue

        started_at = time.perf_counter()

        try:
            with waiting_for_response():
                result = send_prompt(
                    message,
                    explicit_profile=explicit_profile,
                )
        except RouterAPIError as exc:
            _show_api_error(exc)
            continue
        except RouterClientError as exc:
            typer.echo()
            show_error(
                title="Falha ao acessar o Router",
                messages=(str(exc),),
            )
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
