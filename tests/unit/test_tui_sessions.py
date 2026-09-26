import asyncio

from textual.widgets import Static

from villaz_cli.tui.app import VillazApp
from villaz_cli.tui.sessions import (
    SessionListItem,
    SessionListView,
)


def test_sessions_view_starts_empty() -> None:
    async def scenario() -> None:
        app = VillazApp()

        async with app.run_test(
            size=(160, 45),
        ):
            view = SessionListView()

            await app.mount(
                view
            )

            empty = view.query_one(
                "#sessions-empty-state",
                Static,
            )

            assert empty.display is True
            assert (
                str(empty.render())
                == "Nenhuma sessão\nselecionada"
            )

    asyncio.run(
        scenario()
    )


def test_add_session_hides_empty_state() -> None:
    async def scenario() -> None:
        app = VillazApp()

        async with app.run_test(
            size=(160, 45),
        ):
            view = SessionListView()

            await app.mount(
                view
            )

            await view.add_session(
                title="Sessão de teste",
                session_type="efêmera",
                turn_count=0,
            )

            empty = view.query_one(
                "#sessions-empty-state",
                Static,
            )

            assert empty.display is False

    asyncio.run(
        scenario()
    )


def test_session_item_preserves_values() -> None:
    async def scenario() -> None:
        app = VillazApp()

        async with app.run_test(
            size=(160, 45),
        ):
            view = SessionListView()

            await app.mount(
                view
            )

            item = await view.add_session(
                title="Arquitetura",
                session_type="persistente",
                turn_count=8,
            )

            assert item.session_title == "Arquitetura"
            assert item.session_type == "persistente"
            assert item.turn_count == 8

    asyncio.run(
        scenario()
    )


def test_sessions_preserve_order() -> None:
    async def scenario() -> None:
        app = VillazApp()

        async with app.run_test(
            size=(160, 45),
        ):
            view = SessionListView()

            await app.mount(
                view
            )

            first = await view.add_session(
                title="Primeira",
                session_type="efêmera",
                turn_count=1,
            )

            second = await view.add_session(
                title="Segunda",
                session_type="persistente",
                turn_count=2,
            )

            items = tuple(
                view.query(
                    SessionListItem
                )
            )

            assert items == (
                first,
                second,
            )

    asyncio.run(
        scenario()
    )


def test_select_session_keeps_only_one_selected() -> None:
    async def scenario() -> None:
        app = VillazApp()

        async with app.run_test(
            size=(160, 45),
        ):
            view = SessionListView()

            await app.mount(
                view
            )

            first = await view.add_session(
                title="Primeira",
                session_type="efêmera",
                turn_count=1,
                selected=True,
            )

            second = await view.add_session(
                title="Segunda",
                session_type="persistente",
                turn_count=2,
            )

            view.select_session(
                second
            )

            assert first.selected is False
            assert second.selected is True
            assert first.has_class("selected") is False
            assert second.has_class("selected") is True

    asyncio.run(
        scenario()
    )


def test_clear_sessions_restores_empty_state() -> None:
    async def scenario() -> None:
        app = VillazApp()

        async with app.run_test(
            size=(160, 45),
        ):
            view = SessionListView()

            await app.mount(
                view
            )

            await view.add_session(
                title="Teste",
                session_type="efêmera",
                turn_count=0,
            )

            await view.clear_sessions()

            assert (
                len(
                    view.query(
                        SessionListItem
                    )
                )
                == 0
            )

            empty = view.query_one(
                "#sessions-empty-state",
                Static,
            )

            assert empty.display is True

    asyncio.run(
        scenario()
    )
