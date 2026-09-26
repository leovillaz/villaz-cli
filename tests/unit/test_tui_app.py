import asyncio
import threading

from datetime import timezone
from types import SimpleNamespace
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Static, TextArea

from villaz_cli.tui.context import ContextView
from villaz_cli.tui.conversation import (
    ConversationMessage,
    ConversationView,
)
from villaz_cli.tui.sessions import SessionListView
from villaz_cli.tui.app import (
    MEDIUM_MIN_WIDTH,
    WIDE_MIN_WIDTH,
    ComposerSubmitRequested,
    ComposerTextArea,
    VillazApp,
)

from villaz_cli.session import (
    PersistenceMode,
    ProfileModeKind,
    SessionAuthority,
    SessionLifecycle,
)
from villaz_cli.session_stores import (
    EphemeralSessionStateStore,
)
from villaz_cli.conversation import (
    Message as DomainMessage,
    MessageRole,
    Turn,
)
from villaz_cli.http_client import (
    RouterAPIError,
    RouterConnectionError,
    RouterProtocolError,
)

def _commit_fake_execution_turn(
    session,
    current_message: DomainMessage,
    *,
    assistant_content: str = "resposta confirmada",
) -> SimpleNamespace:
    turn = Turn(
        user=current_message,
        assistant=DomainMessage(
            role=MessageRole.ASSISTANT,
            content=assistant_content,
        ),
    )

    session.conversation.append(
        turn
    )

    return SimpleNamespace(
        turn=turn
    )


def test_tui_mounts_full_screen_structure() -> None:
    async def scenario() -> None:
        app = VillazApp()

        async with app.run_test(
            size=(160, 45),
        ):
            assert isinstance(
                app.query_one("#app-header"),
                Static,
            )

            assert isinstance(
                app.query_one("#workspace"),
                Horizontal,
            )

            assert isinstance(
                app.query_one("#sessions-panel"),
                SessionListView,
            )

            assert isinstance(
                app.query_one("#conversation-panel"),
                ConversationView,
            )

            assert isinstance(
                app.query_one("#context-panel"),
                ContextView,
            )

            composer_region = app.query_one(
                "#composer-region",
                Vertical,
            )

            execution_feedback = app.query_one(
                "#execution-feedback",
                Static,
            )

            assert execution_feedback.parent is composer_region

            assert execution_feedback.display is False

            assert str(
                execution_feedback.render()
            ) == ""

            composer = app.query_one(
                "#composer",
                ComposerTextArea,
            )

            assert isinstance(
                composer,
                TextArea,
            )

            assert composer.parent is composer_region

            workspace = app.query_one(
                "#workspace",
                Horizontal,
            )

            assert composer_region.parent is not workspace

            assert isinstance(
                app.query_one("#app-footer"),
                Static,
            )

    asyncio.run(
        scenario()
    )


def test_tui_uses_stable_panel_titles() -> None:
    async def scenario() -> None:
        app = VillazApp()

        async with app.run_test(
            size=(160, 45),
        ):
            sessions = app.query_one(
                "#sessions-panel",
                SessionListView,
            )
            conversation = app.query_one(
                "#conversation-panel",
                ConversationView,
            )
            context = app.query_one(
                "#context-panel",
                ContextView,
            )

            assert sessions.border_title == "SESSÕES"
            assert conversation.border_title == "CONVERSA"
            assert context.border_title == "CONTEXTO ATUAL"

    asyncio.run(
        scenario()
    )


def test_tui_focuses_composer_on_mount() -> None:
    async def scenario() -> None:
        app = VillazApp()

        async with app.run_test(
            size=(160, 45),
        ):
            composer = app.query_one(
                "#composer",
                TextArea,
            )

            assert composer.has_focus is True

    asyncio.run(
        scenario()
    )


def test_tui_composer_is_multiline_soft_wrapped() -> None:
    async def scenario() -> None:
        app = VillazApp()

        async with app.run_test(
            size=(160, 45),
        ):
            composer = app.query_one(
                "#composer",
                TextArea,
            )

            assert composer.soft_wrap is True
            assert composer.show_line_numbers is False
            assert composer.placeholder == (
                "Digite sua mensagem aqui..."
            )

    asyncio.run(
        scenario()
    )


def test_tui_accepts_text_without_executing_conversation() -> None:
    async def scenario() -> None:
        app = VillazApp()

        async with app.run_test(
            size=(160, 45),
        ) as pilot:
            composer = app.query_one(
                "#composer",
                TextArea,
            )

            await pilot.press(
                "o",
                "l",
                "á",
            )

            assert composer.text == "olá"

    asyncio.run(
        scenario()
    )


def test_tui_declares_navigation_shortcuts() -> None:
    bindings = tuple(
        VillazApp.BINDINGS
    )

    assert len(bindings) == 5

    assert all(
        isinstance(binding, Binding)
        for binding in bindings
    )

    assert [
        binding.key
        for binding in bindings
    ] == [
        "f2",
        "f3",
        "f4",
        "f6",
        "ctrl+q",
    ]

    assert [
        binding.action
        for binding in bindings
    ] == [
        "focus_sessions",
        "focus_conversation",
        "focus_context",
        "focus_composer",
        "quit",
    ]

    assert all(
        binding.priority is True
        for binding in bindings
    )


def test_tui_initial_content_contains_only_known_local_state() -> None:
    async def scenario() -> None:
        app = VillazApp()

        async with app.run_test(
            size=(160, 45),
        ):
            context = app.query_one(
                "#context-panel",
                ContextView,
            )

            mode = str(
                context.query_one(
                    "#context-mode",
                    Static,
                ).render()
            )

            session = str(
                context.query_one(
                    "#context-session",
                    Static,
                ).render()
            )

            turns = str(
                context.query_one(
                    "#context-turns",
                    Static,
                ).render()
            )

            rendered = "\n".join(
                (
                    mode,
                    session,
                    turns,
                )
            )

            assert "auto" in rendered
            assert "efêmera" in rendered
            assert "0" in rendered

            assert "Modelo" not in rendered
            assert "Rota" not in rendered
            assert "Tokens" not in rendered
            assert "online" not in rendered

    asyncio.run(
        scenario()
    )


def test_tui_creates_real_ephemeral_session() -> None:
    app = VillazApp()

    assert (
        app.session.persistence_mode
        is PersistenceMode.EPHEMERAL
    )

    assert (
        app.session.authority
        is SessionAuthority.LOCAL
    )

    assert (
        app.session.profile_mode.kind
        is ProfileModeKind.AUTO
    )

    assert (
        app.session.lifecycle
        is SessionLifecycle.ACTIVE
    )

    assert app.session.conversation.turns == ()


def test_tui_executes_submission_in_worker_thread(
    monkeypatch,
) -> None:
    async def scenario() -> None:
        started = threading.Event()
        release = threading.Event()

        captured: dict[str, object] = {}

        ui_thread_id = threading.get_ident()

        def fake_execute_session_message(
            session,
            current_message,
            *,
            updated_at,
            store,
        ):
            captured["session"] = session
            captured["message"] = current_message
            captured["updated_at"] = updated_at
            captured["store"] = store
            captured["thread_id"] = (
                threading.get_ident()
            )

            started.set()

            assert release.wait(
                timeout=2
            )

            result = _commit_fake_execution_turn(
                session,
                current_message,
            )

            captured["result"] = result

            return result

        monkeypatch.setattr(
            "villaz_cli.tui.app.execute_session_message",
            fake_execute_session_message,
        )

        app = VillazApp()

        async with app.run_test(
            size=(160, 45),
        ) as pilot:
            composer = app.query_one(
                "#composer",
                ComposerTextArea,
            )

            original = (
                "  primeira linha\n"
                "segunda linha  "
            )

            composer.load_text(
                original
            )

            await pilot.press(
                "enter"
            )

            assert await asyncio.to_thread(
                started.wait,
                1,
            )

            worker = (
                app._active_execution_worker
            )

            assert worker is not None

            assert app._execution_busy is True

            assert (
                composer.submission_enabled
                is False
            )

            assert composer.text == ""

            feedback = app.query_one(
                "#execution-feedback",
                Static,
            )

            assert feedback.display is True

            assert str(
                feedback.render()
            ) == "Processando..."

            message = captured["message"]

            assert message.role is MessageRole.USER
            assert message.content == original

            assert captured["session"] is app.session
            assert captured["store"] is app.session_store

            assert (
                captured["updated_at"].tzinfo
                is timezone.utc
            )

            assert (
                captured["thread_id"]
                != ui_thread_id
            )

            conversation = app.query_one(
                "#conversation-panel",
                ConversationView,
            )

            assert tuple(
                conversation.query(
                    ConversationMessage
                )
            ) == ()

            release.set()

            result = await worker.wait()

            assert result is captured["result"]

            await pilot.pause()

            assert feedback.display is False

            assert str(
                feedback.render()
            ) == ""

            assert (
                app._last_execution_result
                is captured["result"]
            )

            assert app._last_execution_error is None

            assert app._execution_busy is False

            assert (
                composer.submission_enabled
                is True
            )

            assert composer.has_focus is True

    asyncio.run(
        scenario()
    )


def test_tui_blocks_concurrent_submission(
    monkeypatch,
) -> None:
    async def scenario() -> None:
        started = threading.Event()
        release = threading.Event()

        call_count = 0

        def fake_execute_session_message(
            session,
            current_message,
            *,
            updated_at,
            store,
        ):
            nonlocal call_count

            call_count += 1

            started.set()

            assert release.wait(
                timeout=2
            )

            return _commit_fake_execution_turn(
                session,
                current_message,
            )

        monkeypatch.setattr(
            "villaz_cli.tui.app.execute_session_message",
            fake_execute_session_message,
        )

        app = VillazApp()

        async with app.run_test(
            size=(160, 45),
        ) as pilot:
            composer = app.query_one(
                "#composer",
                ComposerTextArea,
            )

            composer.load_text(
                "primeira"
            )

            await pilot.press(
                "enter"
            )

            assert await asyncio.to_thread(
                started.wait,
                1,
            )

            assert call_count == 1

            composer.load_text(
                "segunda"
            )

            await pilot.press(
                "enter"
            )

            await pilot.pause()

            assert call_count == 1

            release.set()

            worker = (
                app._active_execution_worker
            )

            assert worker is not None

            await worker.wait()

            await pilot.pause()

            assert app._execution_busy is False

    asyncio.run(
        scenario()
    )


def test_tui_maps_execution_errors_to_public_messages() -> None:
    app = VillazApp()

    cases = (
        (
            RouterAPIError(
                code="UNROUTED",
                message="sensitive-unrouted-detail",
            ),
            (
                "Não foi possível selecionar "
                "um perfil automaticamente."
            ),
        ),
        (
            RouterAPIError(
                code="AMBIGUOUS",
                message="sensitive-ambiguous-detail",
            ),
            (
                "A mensagem corresponde a "
                "mais de uma rota possível."
            ),
        ),
        (
            RouterAPIError(
                code="INVALID_PROFILE",
                message="sensitive-profile-detail",
            ),
            "O perfil selecionado não é válido.",
        ),
        (
            RouterAPIError(
                code="CONTEXT_OVERFLOW",
                message="sensitive-context-detail",
            ),
            (
                "A conversa excede o contexto "
                "disponível do modelo."
            ),
        ),
        (
            RouterAPIError(
                code="FUTURE_PUBLIC_CODE",
                message="sensitive-future-detail",
            ),
            (
                "A solicitação foi recusada "
                "pelo Villaz Router."
            ),
        ),
        (
            RouterConnectionError(
                "sensitive-connection-detail"
            ),
            (
                "Não foi possível comunicar "
                "com o Villaz Router."
            ),
        ),
        (
            RouterProtocolError(
                "sensitive-protocol-detail"
            ),
            (
                "O Villaz Router retornou "
                "uma resposta incompatível."
            ),
        ),
        (
            RuntimeError(
                "sensitive-unexpected-detail"
            ),
            (
                "A solicitação não pôde "
                "ser concluída."
            ),
        ),
    )

    for error, expected in cases:
        mapped = app._map_execution_error(
            error
        )

        assert mapped == expected

        assert str(error) not in mapped


def test_tui_releases_composer_after_worker_error(
    monkeypatch,
) -> None:
    async def scenario() -> None:
        def fake_execute_session_message(
            session,
            current_message,
            *,
            updated_at,
            store,
        ):
            raise RuntimeError(
                "falha controlada"
            )

        monkeypatch.setattr(
            "villaz_cli.tui.app.execute_session_message",
            fake_execute_session_message,
        )

        app = VillazApp()

        async with app.run_test(
            size=(160, 45),
        ) as pilot:
            composer = app.query_one(
                "#composer",
                ComposerTextArea,
            )

            original = (
                "  mensagem original\n"
                "segunda linha  "
            )

            composer.load_text(
                original
            )

            await pilot.press(
                "enter"
            )

            for _ in range(100):
                if not app._execution_busy:
                    break

                await asyncio.sleep(
                    0.01
                )

            await pilot.pause()

            assert app._execution_busy is False

            assert isinstance(
                app._last_execution_error,
                RuntimeError,
            )

            assert (
                str(app._last_execution_error)
                == "falha controlada"
            )

            feedback = app.query_one(
                "#execution-feedback",
                Static,
            )

            assert feedback.display is True

            assert str(
                feedback.render()
            ) == (
                "A solicitação não pôde ser concluída."
            )

            assert (
                "falha controlada"
                not in str(
                    feedback.render()
                )
            )

            assert (
                composer.submission_enabled
                is True
            )

            assert composer.has_focus is True

            assert composer.text == original

            assert app.session.conversation.turns == ()

            conversation = app.query_one(
                "#conversation-panel",
                ConversationView,
            )

            assert tuple(
                conversation.query(
                    ConversationMessage
                )
            ) == ()

            context = app.query_one(
                "#context-panel",
                ContextView,
            )

            assert context.turn_count == 0

    asyncio.run(
        scenario()
    )


def test_tui_replaces_previous_error_feedback_on_new_successful_submission(
    monkeypatch,
) -> None:
    async def scenario() -> None:
        second_started = threading.Event()
        second_release = threading.Event()

        call_count = 0

        def fake_execute_session_message(
            session,
            current_message,
            *,
            updated_at,
            store,
        ):
            nonlocal call_count

            call_count += 1

            if call_count == 1:
                raise RouterAPIError(
                    code="UNROUTED",
                    message="sensitive-unrouted-detail",
                )

            second_started.set()

            assert second_release.wait(
                timeout=2
            )

            return _commit_fake_execution_turn(
                session,
                current_message,
                assistant_content="segunda resposta",
            )

        monkeypatch.setattr(
            "villaz_cli.tui.app.execute_session_message",
            fake_execute_session_message,
        )

        app = VillazApp()

        async with app.run_test(
            size=(160, 45),
        ) as pilot:
            composer = app.query_one(
                "#composer",
                ComposerTextArea,
            )

            feedback = app.query_one(
                "#execution-feedback",
                Static,
            )

            conversation = app.query_one(
                "#conversation-panel",
                ConversationView,
            )

            context = app.query_one(
                "#context-panel",
                ContextView,
            )

            first_text = "mensagem sem rota"

            composer.load_text(
                first_text
            )

            await pilot.press(
                "enter"
            )

            for _ in range(100):
                if not app._execution_busy:
                    break

                await asyncio.sleep(
                    0.01
                )

            await pilot.pause()

            assert call_count == 1

            assert composer.text == first_text

            assert feedback.display is True

            assert str(
                feedback.render()
            ) == (
                "Não foi possível selecionar "
                "um perfil automaticamente."
            )

            assert (
                app.session.conversation.turns
                == ()
            )

            assert tuple(
                conversation.query(
                    ConversationMessage
                )
            ) == ()

            assert context.turn_count == 0

            second_text = "segunda mensagem"

            composer.load_text(
                second_text
            )

            await pilot.press(
                "enter"
            )

            assert await asyncio.to_thread(
                second_started.wait,
                1,
            )

            assert call_count == 2

            assert app._execution_busy is True

            assert (
                composer.submission_enabled
                is False
            )

            assert composer.text == ""

            assert feedback.display is True

            assert str(
                feedback.render()
            ) == "Processando..."

            second_release.set()

            worker = (
                app._active_execution_worker
            )

            assert worker is not None

            await worker.wait()

            await pilot.pause()

            assert app._execution_busy is False

            assert (
                composer.submission_enabled
                is True
            )

            assert composer.has_focus is True

            assert composer.text == ""

            assert feedback.display is False

            assert str(
                feedback.render()
            ) == ""

            assert len(
                app.session.conversation.turns
            ) == 1

            messages = tuple(
                conversation.query(
                    ConversationMessage
                )
            )

            assert len(messages) == 2

            assert messages[0].content == second_text

            assert (
                messages[1].content
                == "segunda resposta"
            )

            assert context.turn_count == 1

    asyncio.run(
        scenario()
    )


def test_tui_materializes_confirmed_turn_after_success(
    monkeypatch,
) -> None:
    async def scenario() -> None:
        user_content = (
            "  pergunta do usuário\n"
            "segunda linha  "
        )

        assistant_content = (
            "resposta confirmada"
        )

        def fake_execute_session_message(
            session,
            current_message,
            *,
            updated_at,
            store,
        ):
            return _commit_fake_execution_turn(
                session,
                current_message,
                assistant_content=assistant_content,
            )

        monkeypatch.setattr(
            "villaz_cli.tui.app.execute_session_message",
            fake_execute_session_message,
        )

        app = VillazApp()

        async with app.run_test(
            size=(160, 45),
        ) as pilot:
            composer = app.query_one(
                "#composer",
                ComposerTextArea,
            )

            conversation = app.query_one(
                "#conversation-panel",
                ConversationView,
            )

            context = app.query_one(
                "#context-panel",
                ContextView,
            )

            composer.load_text(
                user_content
            )

            await pilot.press(
                "enter"
            )

            for _ in range(100):
                if not app._execution_busy:
                    break

                await asyncio.sleep(
                    0.01
                )

            await pilot.pause()

            assert app._execution_busy is False

            assert len(
                app.session.conversation.turns
            ) == 1

            messages = tuple(
                conversation.query(
                    ConversationMessage
                )
            )

            assert len(messages) == 2

            assert (
                messages[0].content
                == user_content
            )

            assert (
                messages[1].content
                == assistant_content
            )

            assert messages[0].has_class(
                "user-message"
            )

            assert messages[1].has_class(
                "assistant-message"
            )

            assert context.turn_count == 1

            assert composer.text == ""

            assert (
                composer.submission_enabled
                is True
            )

            assert composer.has_focus is True

    asyncio.run(
        scenario()
    )


def test_tui_uses_ephemeral_session_store() -> None:
    app = VillazApp()

    assert isinstance(
        app.session_store,
        EphemeralSessionStateStore,
    )


def test_tui_context_reflects_real_session_state() -> None:
    async def scenario() -> None:
        app = VillazApp()

        async with app.run_test(
            size=(160, 45),
        ):
            context = app.query_one(
                "#context-panel",
                ContextView,
            )

            assert context.mode == (
                app.session.profile_mode.kind.value
            )

            assert context.session_type == "efêmera"

            assert context.turn_count == len(
                app.session.conversation.turns
            )

            assert context.profile is None

    asyncio.run(
        scenario()
    )


def test_wide_layout_shows_all_three_panels() -> None:
    async def scenario() -> None:
        app = VillazApp()

        async with app.run_test(
            size=(WIDE_MIN_WIDTH, 30),
        ):
            assert app.query_one(
                "#sessions-panel"
            ).display is True

            assert app.query_one(
                "#conversation-panel"
            ).display is True

            assert app.query_one(
                "#context-panel"
            ).display is True

    asyncio.run(
        scenario()
    )


def test_medium_layout_hides_context_only() -> None:
    async def scenario() -> None:
        app = VillazApp()

        async with app.run_test(
            size=(MEDIUM_MIN_WIDTH, 30),
        ):
            assert app.query_one(
                "#sessions-panel"
            ).display is True

            assert app.query_one(
                "#conversation-panel"
            ).display is True

            assert app.query_one(
                "#context-panel"
            ).display is False

    asyncio.run(
        scenario()
    )


def test_narrow_layout_keeps_conversation_and_composer() -> None:
    async def scenario() -> None:
        app = VillazApp()

        async with app.run_test(
            size=(60, 20),
        ):
            assert app.query_one(
                "#sessions-panel"
            ).display is False

            assert app.query_one(
                "#context-panel"
            ).display is False

            assert app.query_one(
                "#conversation-panel"
            ).display is True

            assert app.query_one(
                "#conversation-panel"
            ).region.width > 0

            assert app.query_one(
                "#composer"
            ).region.height > 0

    asyncio.run(
        scenario()
    )


def test_f2_focuses_sessions_when_visible() -> None:
    async def scenario() -> None:
        app = VillazApp()

        async with app.run_test(
            size=(160, 45),
        ) as pilot:
            await pilot.press(
                "f2"
            )

            assert app.query_one(
                "#sessions-panel"
            ).has_focus is True

    asyncio.run(
        scenario()
    )


def test_f3_focuses_conversation() -> None:
    async def scenario() -> None:
        app = VillazApp()

        async with app.run_test(
            size=(160, 45),
        ) as pilot:
            await pilot.press(
                "f3"
            )

            assert app.query_one(
                "#conversation-panel"
            ).has_focus is True

    asyncio.run(
        scenario()
    )


def test_f4_focuses_context_when_visible() -> None:
    async def scenario() -> None:
        app = VillazApp()

        async with app.run_test(
            size=(160, 45),
        ) as pilot:
            await pilot.press(
                "f4"
            )

            assert app.query_one(
                "#context-panel"
            ).has_focus is True

    asyncio.run(
        scenario()
    )


def test_f6_returns_focus_to_composer() -> None:
    async def scenario() -> None:
        app = VillazApp()

        async with app.run_test(
            size=(160, 45),
        ) as pilot:
            await pilot.press(
                "f3"
            )

            assert app.query_one(
                "#conversation-panel"
            ).has_focus is True

            await pilot.press(
                "f6"
            )

            assert app.query_one(
                "#composer"
            ).has_focus is True

    asyncio.run(
        scenario()
    )


class RecordingVillazApp(VillazApp):
    CSS_PATH = None

    def __init__(self) -> None:
        super().__init__()
        self.submitted_messages: list[str] = []

    def on_composer_submit_requested(
        self,
        event: ComposerSubmitRequested,
    ) -> None:
        event.prevent_default()

        self.submitted_messages.append(
            event.text
        )


def test_composer_declares_submit_and_newline_bindings() -> None:
    bindings = tuple(
        ComposerTextArea.BINDINGS
    )

    assert [
        binding.key
        for binding in bindings
    ] == [
        "enter",
        "shift+enter",
    ]

    assert [
        binding.action
        for binding in bindings
    ] == [
        "submit_message",
        "insert_newline",
    ]

    assert all(
        binding.priority is True
        for binding in bindings
    )


def test_enter_requests_submission_with_exact_text() -> None:
    async def scenario() -> None:
        app = RecordingVillazApp()

        async with app.run_test(
            size=(160, 45),
        ) as pilot:
            composer = app.query_one(
                "#composer",
                ComposerTextArea,
            )

            original = "  primeira linha\nsegunda linha  "

            composer.load_text(
                original
            )

            await pilot.press(
                "enter"
            )
            await pilot.pause()

            assert app.submitted_messages == [
                original
            ]

            assert composer.text == original

    asyncio.run(
        scenario()
    )


def test_enter_does_not_submit_whitespace_only_content() -> None:
    async def scenario() -> None:
        app = RecordingVillazApp()

        async with app.run_test(
            size=(160, 45),
        ) as pilot:
            composer = app.query_one(
                "#composer",
                ComposerTextArea,
            )

            composer.load_text(
                " \n\t "
            )

            await pilot.press(
                "enter"
            )
            await pilot.pause()

            assert app.submitted_messages == []

    asyncio.run(
        scenario()
    )


def test_disabled_composer_does_not_request_submission() -> None:
    async def scenario() -> None:
        app = RecordingVillazApp()

        async with app.run_test(
            size=(160, 45),
        ) as pilot:
            composer = app.query_one(
                "#composer",
                ComposerTextArea,
            )

            composer.load_text(
                "mensagem válida"
            )
            composer.set_submission_enabled(
                False
            )

            await pilot.press(
                "enter"
            )
            await pilot.pause()

            assert app.submitted_messages == []

            assert composer.text == (
                "mensagem válida"
            )

    asyncio.run(
        scenario()
    )


def test_shift_enter_inserts_newline_without_submission() -> None:
    async def scenario() -> None:
        app = RecordingVillazApp()

        async with app.run_test(
            size=(160, 45),
        ) as pilot:
            composer = app.query_one(
                "#composer",
                ComposerTextArea,
            )

            await pilot.press(
                "a",
                "b",
                "c",
                "shift+enter",
                "d",
            )
            await pilot.pause()

            assert composer.text == "abc\nd"
            assert app.submitted_messages == []

    asyncio.run(
        scenario()
    )


def test_resize_from_wide_to_narrow_hides_sidebars() -> None:
    async def scenario() -> None:
        app = VillazApp()

        async with app.run_test(
            size=(160, 45),
        ) as pilot:
            assert app.query_one(
                "#sessions-panel"
            ).display is True

            assert app.query_one(
                "#context-panel"
            ).display is True

            await pilot.resize_terminal(
                60,
                20,
            )
            await pilot.pause()

            assert app.query_one(
                "#sessions-panel"
            ).display is False

            assert app.query_one(
                "#context-panel"
            ).display is False

            assert app.query_one(
                "#conversation-panel"
            ).display is True

    asyncio.run(
        scenario()
    )


def test_resize_from_narrow_to_wide_restores_sidebars() -> None:
    async def scenario() -> None:
        app = VillazApp()

        async with app.run_test(
            size=(60, 20),
        ) as pilot:
            assert app.query_one(
                "#sessions-panel"
            ).display is False

            assert app.query_one(
                "#context-panel"
            ).display is False

            await pilot.resize_terminal(
                160,
                45,
            )
            await pilot.pause()

            assert app.query_one(
                "#sessions-panel"
            ).display is True

            assert app.query_one(
                "#context-panel"
            ).display is True

    asyncio.run(
        scenario()
    )


def test_hidden_focused_sidebar_falls_back_to_conversation() -> None:
    async def scenario() -> None:
        app = VillazApp()

        async with app.run_test(
            size=(160, 45),
        ) as pilot:
            await pilot.press(
                "f4"
            )

            assert app.query_one(
                "#context-panel"
            ).has_focus is True

            await pilot.resize_terminal(
                90,
                30,
            )
            await pilot.pause()

            assert app.query_one(
                "#context-panel"
            ).display is False

            assert app.query_one(
                "#conversation-panel"
            ).has_focus is True

    asyncio.run(
        scenario()
    )


def test_footer_changes_with_terminal_width() -> None:
    async def scenario() -> None:
        app = VillazApp()

        async with app.run_test(
            size=(160, 45),
        ) as pilot:
            footer = app.query_one(
                "#app-footer",
                Static,
            )

            wide = str(
                footer.render()
            )

            assert "F2 Sessões" in wide
            assert "F3 Conversa" in wide
            assert "F4 Contexto" in wide
            assert "F6 Mensagem" in wide
            assert "Ctrl+Q Sair" in wide

            await pilot.resize_terminal(
                60,
                20,
            )
            await pilot.pause()

            narrow = str(
                footer.render()
            )

            assert "F3 Conversa" in narrow
            assert "F6 Mensagem" in narrow
            assert "Ctrl+Q Sair" in narrow

            assert "F2 Sessões" not in narrow
            assert "F4 Contexto" not in narrow

    asyncio.run(
        scenario()
    )
