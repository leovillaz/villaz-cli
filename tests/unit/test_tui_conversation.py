import asyncio

from textual.widgets import Static

from villaz_cli.tui.app import VillazApp
from villaz_cli.tui.conversation import (
    ConversationMessage,
    ConversationMessageRole,
    ConversationView,
)


def test_conversation_view_starts_with_empty_state() -> None:
    async def scenario() -> None:
        app = VillazApp()

        async with app.run_test(
            size=(160, 45),
        ):
            view = app.query_one(
                "#conversation-panel",
                ConversationView,
            )

            empty = view.query_one(
                "#conversation-empty-state",
                Static,
            )

            assert empty.display is True
            assert (
                str(empty.render())
                == "Inicie uma conversa para começar."
            )

            assert (
                len(
                    view.query(
                        ConversationMessage
                    )
                )
                == 0
            )

    asyncio.run(
        scenario()
    )


def test_first_message_hides_empty_state() -> None:
    async def scenario() -> None:
        app = VillazApp()

        async with app.run_test(
            size=(160, 45),
        ):
            view = app.query_one(
                "#conversation-panel",
                ConversationView,
            )

            await view.append_user_message(
                "Olá."
            )

            empty = view.query_one(
                "#conversation-empty-state",
                Static,
            )

            assert empty.display is False

    asyncio.run(
        scenario()
    )


def test_user_message_preserves_literal_content() -> None:
    async def scenario() -> None:
        app = VillazApp()

        async with app.run_test(
            size=(160, 45),
        ):
            view = app.query_one(
                "#conversation-panel",
                ConversationView,
            )

            message = await view.append_user_message(
                "[red]texto literal[/red]",
                timestamp="18:55",
            )

            assert (
                message.role
                is ConversationMessageRole.USER
            )

            assert message.content == (
                "[red]texto literal[/red]"
            )

            content = message.query_one(
                ".message-content",
                Static,
            )

            assert str(content.render()) == (
                "[red]texto literal[/red]"
            )

    asyncio.run(
        scenario()
    )


def test_assistant_message_preserves_literal_content() -> None:
    async def scenario() -> None:
        app = VillazApp()

        async with app.run_test(
            size=(160, 45),
        ):
            view = app.query_one(
                "#conversation-panel",
                ConversationView,
            )

            message = await view.append_assistant_message(
                "Resposta\nem duas linhas.",
            )

            assert (
                message.role
                is ConversationMessageRole.ASSISTANT
            )

            assert message.content == (
                "Resposta\nem duas linhas."
            )

            content = message.query_one(
                ".message-content",
                Static,
            )

            assert str(content.render()) == (
                "Resposta\nem duas linhas."
            )

    asyncio.run(
        scenario()
    )


def test_messages_preserve_chronological_order() -> None:
    async def scenario() -> None:
        app = VillazApp()

        async with app.run_test(
            size=(160, 45),
        ):
            view = app.query_one(
                "#conversation-panel",
                ConversationView,
            )

            first = await view.append_user_message(
                "primeira"
            )

            second = await view.append_assistant_message(
                "segunda"
            )

            third = await view.append_user_message(
                "terceira"
            )

            messages = tuple(
                view.query(
                    ConversationMessage
                )
            )

            assert messages == (
                first,
                second,
                third,
            )

    asyncio.run(
        scenario()
    )


def test_assistant_metadata_is_rendered_when_provided() -> None:
    async def scenario() -> None:
        app = VillazApp()

        async with app.run_test(
            size=(160, 45),
        ):
            view = app.query_one(
                "#conversation-panel",
                ConversationView,
            )

            message = await view.append_assistant_message(
                "Resposta.",
                profile="unity-dev",
                elapsed_seconds=2.31,
                output_tokens=42,
            )

            metadata = message.query_one(
                ".message-metadata",
                Static,
            )

            rendered = str(
                metadata.render()
            )

            assert "unity-dev" in rendered
            assert "2.31s" in rendered
            assert "42 tokens" in rendered

    asyncio.run(
        scenario()
    )


def test_metadata_is_absent_when_not_provided() -> None:
    async def scenario() -> None:
        app = VillazApp()

        async with app.run_test(
            size=(160, 45),
        ):
            view = app.query_one(
                "#conversation-panel",
                ConversationView,
            )

            message = await view.append_assistant_message(
                "Sem metadados."
            )

            assert (
                len(
                    message.query(
                        ".message-metadata"
                    )
                )
                == 0
            )

    asyncio.run(
        scenario()
    )


def test_timestamp_is_optional_and_rendered_when_present() -> None:
    async def scenario() -> None:
        app = VillazApp()

        async with app.run_test(
            size=(160, 45),
        ):
            view = app.query_one(
                "#conversation-panel",
                ConversationView,
            )

            message = await view.append_user_message(
                "mensagem",
                timestamp="18:58",
            )

            header = message.query_one(
                ".message-header",
                Static,
            )

            rendered = str(
                header.render()
            )

            assert "VOCÊ" in rendered
            assert "18:58" in rendered

    asyncio.run(
        scenario()
    )


def test_clear_messages_restores_empty_state() -> None:
    async def scenario() -> None:
        app = VillazApp()

        async with app.run_test(
            size=(160, 45),
        ):
            view = app.query_one(
                "#conversation-panel",
                ConversationView,
            )

            await view.append_user_message(
                "pergunta"
            )

            await view.append_assistant_message(
                "resposta"
            )

            await view.clear_messages()

            assert (
                len(
                    view.query(
                        ConversationMessage
                    )
                )
                == 0
            )

            empty = view.query_one(
                "#conversation-empty-state",
                Static,
            )

            assert empty.display is True

    asyncio.run(
        scenario()
    )


def test_conversation_view_remains_focusable() -> None:
    async def scenario() -> None:
        app = VillazApp()

        async with app.run_test(
            size=(160, 45),
        ) as pilot:
            await pilot.press(
                "f3"
            )

            view = app.query_one(
                "#conversation-panel",
                ConversationView,
            )

            assert view.has_focus is True

    asyncio.run(
        scenario()
    )


def test_messages_do_not_change_when_conversation_receives_focus() -> None:
    async def scenario() -> None:
        app = VillazApp()

        async with app.run_test(
            size=(160, 45),
        ) as pilot:
            view = app.query_one(
                "#conversation-panel",
                ConversationView,
            )

            message = await view.append_user_message(
                "conteúdo invariável"
            )

            content = message.query_one(
                ".message-content",
                Static,
            )

            before = str(
                content.render()
            )

            await pilot.press(
                "f3"
            )

            after = str(
                content.render()
            )

            assert before == "conteúdo invariável"
            assert after == before

    asyncio.run(
        scenario()
    )


def test_many_messages_remain_inside_conversation_view() -> None:
    async def scenario() -> None:
        app = VillazApp()

        async with app.run_test(
            size=(100, 20),
        ):
            view = app.query_one(
                "#conversation-panel",
                ConversationView,
            )

            for index in range(20):
                await view.append_user_message(
                    f"mensagem {index}"
                )

            messages = tuple(
                view.query(
                    ConversationMessage
                )
            )

            assert len(messages) == 20

            assert all(
                message.parent is view
                for message in messages
            )

    asyncio.run(
        scenario()
    )


def test_composer_remains_independent_from_conversation_messages() -> None:
    async def scenario() -> None:
        app = VillazApp()

        async with app.run_test(
            size=(160, 45),
        ) as pilot:
            view = app.query_one(
                "#conversation-panel",
                ConversationView,
            )

            await view.append_user_message(
                "histórico"
            )

            await pilot.press(
                "f6"
            )

            composer = app.query_one(
                "#composer"
            )

            await pilot.press(
                "n",
                "o",
                "v",
                "a",
            )

            assert composer.text == "nova"

            messages = tuple(
                view.query(
                    ConversationMessage
                )
            )

            assert len(messages) == 1
            assert messages[0].content == "histórico"

    asyncio.run(
        scenario()
    )
