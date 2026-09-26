import sys
from collections.abc import Iterator
from contextlib import contextmanager
from importlib import metadata
from typing import Annotated

import typer

from villaz_cli.presentation import show_help


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


@contextmanager
def _tty_without_ixon() -> Iterator[None]:
    if not sys.stdin.isatty():
        yield
        return

    try:
        import termios
    except ImportError:
        yield
        return

    try:
        file_descriptor = sys.stdin.fileno()
        original_attributes = termios.tcgetattr(
            file_descriptor
        )
    except (
        OSError,
        ValueError,
        termios.error,
    ):
        yield
        return

    if not (
        original_attributes[0]
        & termios.IXON
    ):
        yield
        return

    updated_attributes = (
        original_attributes.copy()
    )
    updated_attributes[0] &= ~termios.IXON

    try:
        termios.tcsetattr(
            file_descriptor,
            termios.TCSANOW,
            updated_attributes,
        )
    except (
        OSError,
        termios.error,
    ):
        yield
        return

    try:
        yield
    finally:
        termios.tcsetattr(
            file_descriptor,
            termios.TCSANOW,
            original_attributes,
        )

def _run_tui() -> None:
    from villaz_cli.tui import VillazApp

    with _tty_without_ixon():
        VillazApp().run()


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
    _run_tui()


def main() -> None:
    app(prog_name="villaz")
