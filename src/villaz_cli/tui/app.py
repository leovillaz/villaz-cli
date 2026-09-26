from textual import events, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message as TextualMessage
from textual.worker import Worker, WorkerState
from textual.widgets import Static, TextArea

from villaz_cli.tui.context import ContextView
from villaz_cli.tui.conversation import ConversationView
from villaz_cli.tui.sessions import SessionListView
from villaz_cli.tui.profile import (
    ProfileSelectionScreen,
)

from datetime import datetime, timezone

from villaz_cli.session import (
    PersistenceMode,
    ProfileMode,
)
from villaz_cli.session_factory import (
    create_ephemeral_session,
)
from villaz_cli.session_stores import (
    EphemeralSessionStateStore,
)
from villaz_cli.conversation import (
    Message as ConversationMessage,
    MessageRole,
)
from villaz_cli.conversation_execution import (
    SessionMessageExecutionResult,
    execute_session_message,
)
from villaz_cli.http_client import (
    RouterAPIError,
    RouterConnectionError,
    RouterProtocolError,
)
from villaz_cli.session_persistence import (
    change_profile_mode_with_autosave,
)

WIDE_MIN_WIDTH = 120
MEDIUM_MIN_WIDTH = 80


class ComposerSubmitRequested(TextualMessage):
    """Request emitted when the composer contains a valid message to send."""

    def __init__(
        self,
        text: str,
    ) -> None:
        super().__init__()
        self.text = text


class ComposerTextArea(TextArea):
    """Multiline composer with explicit chat submission semantics."""

    BINDINGS = [
        Binding(
            "enter",
            "submit_message",
            show=False,
            priority=True,
        ),
        Binding(
            "shift+enter",
            "insert_newline",
            show=False,
            priority=True,
        ),
    ]

    submission_enabled: bool = True

    def action_submit_message(self) -> None:
        if not self.submission_enabled:
            return

        text = self.text

        if not text.strip():
            return

        self.post_message(
            ComposerSubmitRequested(text)
        )

    def action_insert_newline(self) -> None:
        self.insert("\n")

    def set_submission_enabled(
        self,
        enabled: bool,
    ) -> None:
        self.submission_enabled = enabled


class FocusablePanel(Static):
    """Static panel that participates in keyboard focus navigation."""

    can_focus = True


class ResponsiveWorkspace(Horizontal):
    """Workspace that propagates terminal width changes to the app."""

    def on_resize(
        self,
        event: events.Resize,
    ) -> None:
        app = self.app

        if isinstance(app, VillazApp):
            app.apply_responsive_layout(
                event.size.width
            )


class VillazApp(App[None]):
    """Full-screen terminal interface for Villaz-Lab CLI."""

    CSS_PATH = "villaz.tcss"

    TITLE = "VILLAZ CLI"
    SUB_TITLE = "Interface local para o Villaz-Lab"

    BINDINGS = [
        Binding(
            "f2",
            "focus_sessions",
            "Sessões",
            priority=True,
        ),
        Binding(
            "f3",
            "focus_conversation",
            "Conversa",
            priority=True,
        ),
        Binding(
            "f4",
            "focus_context",
            "Contexto",
            priority=True,
        ),
        Binding(
            "f5",
            "select_profile",
            "Profile",
            priority=True,
        ),
        Binding(
            "f6",
            "focus_composer",
            "Mensagem",
            priority=True,
        ),
        Binding(
            "ctrl+q",
            "quit",
            "Sair",
            priority=True,
        ),
    ]

    def __init__(self) -> None:
        super().__init__()

        created_at = datetime.now(
            timezone.utc
        )

        self.session = create_ephemeral_session(
            created_at=created_at,
        )

        self.session_store = (
            EphemeralSessionStateStore()
        )

        self._execution_busy = False

        self._active_submission_text: str | None = None

        self._active_execution_worker: Worker | None = None

        self._last_execution_result: (
            SessionMessageExecutionResult | None
        ) = None

        self._last_execution_error: BaseException | None = None

    def compose(self) -> ComposeResult:
        yield Static(
            "[b]VILLAZ CLI[/b]"
            "  [dim]│  Seu parceiro de desenvolvimento com IA[/dim]",
            id="app-header",
        )

        with ResponsiveWorkspace(id="workspace"):
            sessions_panel = SessionListView(
                id="sessions-panel",
            )
            sessions_panel.border_title = "SESSÕES"
            yield sessions_panel

            conversation_panel = ConversationView(
                id="conversation-panel",
            )
            conversation_panel.border_title = "CONVERSA"
            yield conversation_panel

            context_panel = ContextView(
                mode=self.session.profile_mode.kind.value,
                session_type=self._session_type_label(),
                turn_count=len(
                    self.session.conversation.turns
                ),
                profile=self.session.profile_mode.profile_id,
                id="context-panel",
            )
            context_panel.border_title = "CONTEXTO ATUAL"
            yield context_panel

        with Vertical(id="composer-region"):
            yield Static(
                "MENSAGEM",
                id="composer-title",
            )

            execution_feedback = Static(
                "",
                id="execution-feedback",
                markup=False,
            )
            execution_feedback.display = False
            yield execution_feedback

            yield ComposerTextArea(
                "",
                id="composer",
                placeholder="Digite sua mensagem aqui...",
                soft_wrap=True,
                show_line_numbers=False,
            )

        yield Static(
            "",
            id="app-footer",
        )

    def on_mount(self) -> None:
        self.apply_responsive_layout(
            self.size.width
        )

        self.query_one(
            "#composer",
            ComposerTextArea,
        ).focus()

    def apply_responsive_layout(
        self,
        width: int,
    ) -> None:
        sessions = self.query_one(
            "#sessions-panel",
            SessionListView,
        )
        conversation = self.query_one(
            "#conversation-panel",
            ConversationView,
        )
        context = self.query_one(
            "#context-panel",
            ContextView,
        )
        footer = self.query_one(
            "#app-footer",
            Static,
        )

        if width >= WIDE_MIN_WIDTH:
            sessions.display = True
            context.display = True

            footer.update(
                "F2 Sessões"
                "  •  F3 Conversa"
                "  •  F4 Contexto"
                "  •  F5 Profile"
                "  •  F6 Mensagem"
                "  •  Ctrl+Q Sair"
            )

        elif width >= MEDIUM_MIN_WIDTH:
            sessions.display = True
            context.display = False

            footer.update(
                "F2 Sessões"
                "  •  F3 Conversa"
                "  •  F5 Profile"
                "  •  F6 Mensagem"
                "  •  Ctrl+Q Sair"
            )

        else:
            sessions.display = False
            context.display = False

            footer.update(
                "F3 Conversa"
                "  •  F5 Profile"
                "  •  F6 Mensagem"
                "  •  Ctrl+Q Sair"
            )

        focused = self.screen.focused

        if (
            focused is sessions
            and not sessions.display
        ):
            conversation.focus()

        if (
            focused is context
            and not context.display
        ):
            conversation.focus()

    def on_composer_submit_requested(
        self,
        event: ComposerSubmitRequested,
    ) -> None:
        if self._execution_busy:
            return

        composer = self.query_one(
            "#composer",
            ComposerTextArea,
        )

        self._execution_busy = True
        self._active_submission_text = event.text
        self._last_execution_result = None
        self._last_execution_error = None

        composer.set_submission_enabled(
            False
        )

        composer.load_text("")

        self._set_execution_feedback(
           "Processando..."
        )

        current_message = ConversationMessage(
            role=MessageRole.USER,
            content=event.text,
        )

        self._active_execution_worker = (
            self._execute_session_message_worker(
                current_message
            )
        )

    def action_focus_conversation(self) -> None:
        self.query_one(
            "#conversation-panel",
            ConversationView,
        ).focus()

    def action_focus_sessions(self) -> None:
        panel = self.query_one(
            "#sessions-panel",
            SessionListView,
        )

        if panel.display:
            panel.focus()

    def action_focus_context(self) -> None:
        panel = self.query_one(
            "#context-panel",
            ContextView,
        )

        if panel.display:
            panel.focus()

    def action_select_profile(self) -> None:
        if self._execution_busy:
            return

        self.push_screen(
            ProfileSelectionScreen(
                current_mode=(
                    self.session.profile_mode
                )
            ),
            self._apply_profile_selection,
    )

    def _apply_profile_selection(
        self,
        profile_mode: ProfileMode | None,
    ) -> None:
        if profile_mode is None:
            return

        if (
            profile_mode
            == self.session.profile_mode
        ):
            return

        change_profile_mode_with_autosave(
            self.session,
            profile_mode,
            updated_at=datetime.now(
                timezone.utc
            ),
            store=self.session_store,
        )

        context = self.query_one(
            "#context-panel",
            ContextView,
        )

        context.set_mode(
            self.session.profile_mode.kind.value
        )

        context.set_profile(
            self.session.profile_mode.profile_id
        )


    def action_focus_composer(self) -> None:
        self.query_one(
            "#composer",
            ComposerTextArea,
        ).focus()

    @work(
        name="conversation-execution",
        group="conversation",
        exit_on_error=False,
        thread=True,
    )
    def _execute_session_message_worker(
        self,
        current_message: ConversationMessage,
    ) -> SessionMessageExecutionResult:
        return execute_session_message(
            self.session,
            current_message,
            updated_at=datetime.now(
                timezone.utc
            ),
            store=self.session_store,
        )

    async def on_worker_state_changed(
        self,
        event: Worker.StateChanged,
    ) -> None:
        if (
            event.worker
            is not self._active_execution_worker
        ):
            return

        if event.state is WorkerState.SUCCESS:
            result = event.worker.result

            self._last_execution_result = result

            await self._apply_successful_execution(
                result
            )

            self._set_execution_feedback(
                None
            )

            self._finish_execution()

            return

        if event.state is WorkerState.ERROR:
            error = event.worker.error

            self._last_execution_error = error

            self._restore_failed_submission()

            self._set_execution_feedback(
                self._map_execution_error(
                    error
                ),
                is_error=True,
            )

            self._finish_execution()

    async def _apply_successful_execution(
        self,
        result: SessionMessageExecutionResult,
    ) -> None:
        conversation = self.query_one(
            "#conversation-panel",
            ConversationView,
        )

        await conversation.append_user_message(
            result.turn.user.content
        )

        await conversation.append_assistant_message(
            result.turn.assistant.content
        )

        context = self.query_one(
            "#context-panel",
            ContextView,
        )

        context.set_turn_count(
            len(
                self.session.conversation.turns
            )
        )

    def _restore_failed_submission(self) -> None:
        original_text = (
            self._active_submission_text
        )

        if original_text is None:
            return

        composer = self.query_one(
            "#composer",
            ComposerTextArea,
        )

        composer.load_text(
            original_text
        )


    def _map_execution_error(
        self,
        error: BaseException | None,
    ) -> str:
        if isinstance(
            error,
            RouterAPIError,
        ):
            return {
                "UNROUTED": (
                    "Não foi possível selecionar "
                    "um perfil automaticamente."
                ),
                "AMBIGUOUS": (
                    "A mensagem corresponde a "
                    "mais de uma rota possível."
                ),
                "INVALID_PROFILE": (
                    "O perfil selecionado não é válido."
                ),
                "CONTEXT_OVERFLOW": (
                    "A conversa excede o contexto "
                    "disponível do modelo."
                ),
            }.get(
                error.code,
                (
                    "A solicitação foi recusada "
                    "pelo Villaz Router."
                ),
            )

        if isinstance(
            error,
            RouterConnectionError,
        ):
            return (
                "Não foi possível comunicar "
                "com o Villaz Router."
            )

        if isinstance(
            error,
            RouterProtocolError,
        ):
            return (
                "O Villaz Router retornou "
                "uma resposta incompatível."
            )

        return (
            "A solicitação não pôde ser concluída."
        )

    def _set_execution_feedback(
        self,
        text: str | None,
        *,
        is_error: bool = False,
    ) -> None:
        feedback = self.query_one(
            "#execution-feedback",
            Static,
        )

        feedback.set_class(
            is_error,
            "error",
        )

        if text is None:
            feedback.update("")
            feedback.display = False
            return

        feedback.update(
            text
        )
        feedback.display = True


    def _session_type_label(self) -> str:
        if (
            self.session.persistence_mode
            is PersistenceMode.EPHEMERAL
        ):
            return "efêmera"

        return "persistente"

    def _finish_execution(self) -> None:
        self._execution_busy = False
        self._active_execution_worker = None

        composer = self.query_one(
            "#composer",
            ComposerTextArea,
        )

        composer.set_submission_enabled(
            True
        )

        composer.focus()

        self._active_submission_text = None