from __future__ import annotations

from collections.abc import Iterable

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Static

from villaz_cli.session import SessionLifecycle
from villaz_cli.session_query import SessionSummary


EMPTY_SESSIONS_MESSAGE = "Nenhuma sessão\nselecionada"
SESSION_LOAD_ERROR_MESSAGE = "Não foi possível carregar as sessões salvas."


class SessionListItem(Vertical):
    """Presentation-only item representing one session."""

    def __init__(
        self,
        *,
        session_id: str,
        title: str,
        session_type: str,
        turn_count: int,
        selected: bool = False,
    ) -> None:
        super().__init__()

        self.session_id = session_id
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
            EMPTY_SESSIONS_MESSAGE,
            id="sessions-empty-state",
            markup=False,
        )

    async def add_session(
        self,
        *,
        session_id: str,
        title: str,
        session_type: str,
        turn_count: int,
        selected: bool = False,
    ) -> SessionListItem:
        if selected:
            self._clear_selection()

        item = SessionListItem(
            session_id=session_id,
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

    async def add_session_summary(
        self,
        summary: SessionSummary,
    ) -> SessionListItem | None:
        if summary.lifecycle is SessionLifecycle.DELETED:
            return None

        return await self.add_session(
            session_id=summary.session_id,
            title=f"Sessão {summary.session_id[:8]}",
            session_type="persistente",
            turn_count=summary.turn_count,
        )

    async def set_session_summaries(
        self,
        summaries: Iterable[SessionSummary],
    ) -> None:
        await self.clear_sessions()

        for summary in summaries:
            await self.add_session_summary(summary)

    async def show_load_error(self) -> None:
        await self.clear_sessions()
        self.query_one(
            "#sessions-empty-state",
            Static,
        ).update(SESSION_LOAD_ERROR_MESSAGE)

    def get_session_item(
        self,
        session_id: str,
    ) -> SessionListItem | None:
        for item in self.query(SessionListItem):
            if item.session_id == session_id:
                return item

        return None

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

        empty_state.update(EMPTY_SESSIONS_MESSAGE)
        empty_state.display = True

    def _clear_selection(self) -> None:
        for item in self.query(
            SessionListItem
        ):
            item.set_selected(False)
