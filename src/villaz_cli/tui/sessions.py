from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Static


class SessionListItem(Vertical):
    """Presentation-only item representing one session."""

    def __init__(
        self,
        *,
        title: str,
        session_type: str,
        turn_count: int,
        selected: bool = False,
    ) -> None:
        super().__init__()

        self.session_title = title
        self.session_type = session_type
        self.turn_count = turn_count
        self.selected = selected

        self.add_class("session-list-item")

        if selected:
            self.add_class("selected")

    def compose(self) -> ComposeResult:
        yield Static(
            self.session_title,
            classes="session-item-title",
            markup=False,
        )

        yield Static(
            f"{self.session_type}  •  {self.turn_count} turns",
            classes="session-item-metadata",
            markup=False,
        )

    def set_selected(
        self,
        selected: bool,
    ) -> None:
        self.selected = selected
        self.set_class(
            selected,
            "selected",
        )


class SessionListView(VerticalScroll):
    """Scrollable presentation-only session list."""

    can_focus = True

    def compose(self) -> ComposeResult:
        yield Static(
            "Nenhuma sessão\nselecionada",
            id="sessions-empty-state",
            markup=False,
        )

    async def add_session(
        self,
        *,
        title: str,
        session_type: str,
        turn_count: int,
        selected: bool = False,
    ) -> SessionListItem:
        if selected:
            self._clear_selection()

        item = SessionListItem(
            title=title,
            session_type=session_type,
            turn_count=turn_count,
            selected=selected,
        )

        empty_state = self.query_one(
            "#sessions-empty-state",
            Static,
        )

        empty_state.display = False

        await self.mount(
            item
        )

        return item

    def select_session(
        self,
        item: SessionListItem,
    ) -> None:
        self._clear_selection()
        item.set_selected(True)

    async def clear_sessions(self) -> None:
        items = tuple(
            self.query(
                SessionListItem
            )
        )

        for item in items:
            await item.remove()

        empty_state = self.query_one(
            "#sessions-empty-state",
            Static,
        )

        empty_state.display = True

    def _clear_selection(self) -> None:
        for item in self.query(
            SessionListItem
        ):
            item.set_selected(False)
