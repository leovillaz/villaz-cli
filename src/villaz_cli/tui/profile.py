from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static

from villaz_cli.session import (
    ProfileMode,
    ProfileModeKind,
)


class ProfileSelectionScreen(
    ModalScreen[ProfileMode | None]
):
    """Modal for selecting automatic or explicit profile mode."""

    BINDINGS = [
        Binding(
            "escape",
            "cancel",
            "Cancelar",
            show=False,
            priority=True,
        ),
    ]

    def __init__(
        self,
        *,
        current_mode: ProfileMode,
    ) -> None:
        super().__init__()

        self.current_mode = current_mode

    def compose(self) -> ComposeResult:
        with Vertical(id="profile-dialog"):
            yield Static(
                "PROFILE",
                id="profile-dialog-title",
                markup=False,
            )

            yield Static(
                self._current_mode_text(),
                id="profile-current-mode",
                markup=False,
            )

            yield Static(
                "Profile explícito",
                id="profile-input-label",
                markup=False,
            )

            yield Input(
                value=(
                    self.current_mode.profile_id
                    or ""
                ),
                placeholder=(
                    "Ex.: code-review-security"
                ),
                id="profile-input",
            )

            yield Static(
                "",
                id="profile-validation-message",
                markup=False,
            )

            with Horizontal(
                id="profile-actions"
            ):
                yield Button(
                    "Automático",
                    id="profile-auto",
                )

                yield Button(
                    "Aplicar",
                    id="profile-apply",
                    variant="primary",
                )

                yield Button(
                    "Cancelar",
                    id="profile-cancel",
                )

    def on_mount(self) -> None:
        validation = self.query_one(
            "#profile-validation-message",
            Static,
        )

        validation.display = False

        self.query_one(
            "#profile-input",
            Input,
        ).focus()

    def on_button_pressed(
        self,
        event: Button.Pressed,
    ) -> None:
        button_id = event.button.id

        if button_id == "profile-auto":
            self.dismiss(
                ProfileMode.auto()
            )
            return

        if button_id == "profile-apply":
            self._apply_explicit_profile()
            return

        if button_id == "profile-cancel":
            self.dismiss(None)

    def on_input_submitted(
        self,
        event: Input.Submitted,
    ) -> None:
        if event.input.id != "profile-input":
            return

        self._apply_explicit_profile()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _apply_explicit_profile(self) -> None:
        profile_input = self.query_one(
            "#profile-input",
            Input,
        )

        profile_id = (
            profile_input.value.strip()
        )

        if not profile_id:
            validation = self.query_one(
                "#profile-validation-message",
                Static,
            )

            validation.update(
                "Informe um profile ou "
                "escolha Automático."
            )
            validation.display = True

            profile_input.focus()
            return

        self.dismiss(
            ProfileMode.explicit(
                profile_id
            )
        )

    def _current_mode_text(self) -> str:
        if (
            self.current_mode.kind
            is ProfileModeKind.AUTO
        ):
            return (
                "Modo atual: automático"
            )

        return (
            "Modo atual: explícito"
            f" • {self.current_mode.profile_id}"
        )
