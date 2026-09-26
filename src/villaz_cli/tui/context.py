from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static


class ContextView(Vertical):
    """Presentation-only view of the current conversation context."""

    can_focus = True

    def __init__(
        self,
        *,
        mode: str = "auto",
        session_type: str = "efêmera",
        turn_count: int = 0,
        profile: str | None = None,
        id: str | None = None,
    ) -> None:
        super().__init__(
            id=id,
        )

        self.mode = mode
        self.session_type = session_type
        self.turn_count = turn_count
        self.profile = profile

    def compose(self) -> ComposeResult:
        yield Static(
            "",
            id="context-mode",
            markup=False,
        )

        yield Static(
            "",
            id="context-session",
            markup=False,
        )

        yield Static(
            "",
            id="context-turns",
            markup=False,
        )

        yield Static(
            "",
            id="context-profile",
            markup=False,
        )

    def on_mount(self) -> None:
        self._refresh_values()

    def set_mode(
        self,
        mode: str,
    ) -> None:
        self.mode = mode

        if self.is_mounted:
            self._refresh_values()

    def set_session_type(
        self,
        session_type: str,
    ) -> None:
        self.session_type = session_type

        if self.is_mounted:
            self._refresh_values()

    def set_turn_count(
        self,
        turn_count: int,
    ) -> None:
        self.turn_count = turn_count

        if self.is_mounted:
            self._refresh_values()

    def set_profile(
        self,
        profile: str | None,
    ) -> None:
        self.profile = profile

        if self.is_mounted:
            self._refresh_values()

    def _refresh_values(self) -> None:
        self.query_one(
            "#context-mode",
            Static,
        ).update(
            f"Modo      {self.mode}"
        )

        self.query_one(
            "#context-session",
            Static,
        ).update(
            f"Sessão    {self.session_type}"
        )

        self.query_one(
            "#context-turns",
            Static,
        ).update(
            f"Turns     {self.turn_count}"
        )

        profile_widget = self.query_one(
            "#context-profile",
            Static,
        )

        if self.profile is None:
            profile_widget.update("")
            profile_widget.display = False
            return

        profile_widget.update(
            f"Profile   {self.profile}"
        )
        profile_widget.display = True
