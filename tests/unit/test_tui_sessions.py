import asyncio
from datetime import datetime, timezone
from unittest.mock import patch

from textual.widgets import Static

from villaz_cli.session import (
    PersistenceMode,
    ProfileMode,
    SessionAuthority,
    SessionLifecycle,
)
from villaz_cli.session_query import SessionSummary
from villaz_cli.tui.app import VillazApp
from villaz_cli.tui.sessions import (
    SessionListItem,
    SessionListView,
)


def make_summary(
    session_id: str,
    *,
    lifecycle: SessionLifecycle = SessionLifecycle.ACTIVE,
    turn_count: int = 0,
) -> SessionSummary:
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return SessionSummary(
        session_id=session_id,
        lifecycle=lifecycle,
        persistence_mode=PersistenceMode.PERSISTENT,
        authority=SessionAuthority.LOCAL,
        profile_mode=ProfileMode.auto(),
        created_at=timestamp,
        updated_at=timestamp,
        turn_count=turn_count,
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
                session_id="session-test",
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
                session_id="session-architecture",
                title="Arquitetura",
                session_type="persistente",
                turn_count=8,
            )

            assert item.session_id == "session-architecture"
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
                session_id="session-first",
                title="Primeira",
                session_type="efêmera",
                turn_count=1,
            )

            second = await view.add_session(
                session_id="session-second",
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
                session_id="session-first",
                title="Primeira",
                session_type="efêmera",
                turn_count=1,
                selected=True,
            )

            second = await view.add_session(
                session_id="session-second",
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
                session_id="session-test",
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


def test_add_session_summary_maps_active_and_closed_without_backend_calls() -> None:
    async def scenario() -> None:
        app = VillazApp()

        async with app.run_test(size=(160, 45)):
            view = SessionListView()
            await app.mount(view)

            active = make_summary(
                "12345678-aaaa-bbbb-cccc-123456789abc",
                turn_count=3,
            )
            closed = make_summary(
                "87654321-aaaa-bbbb-cccc-123456789abc",
                lifecycle=SessionLifecycle.CLOSED,
                turn_count=7,
            )

            with (
                patch("villaz_cli.session_query.list_persisted_sessions") as list_sessions,
                patch("villaz_cli.session_query.load_session") as load_session,
                patch("villaz_cli.session_persistence.persist_session") as persist_session,
                patch("villaz_cli.session_persistence.resume_session") as resume_session,
            ):
                first = await view.add_session_summary(active)
                second = await view.add_session_summary(closed)

            assert first is not None
            assert second is not None
            assert first.session_id == active.session_id
            assert second.session_id == closed.session_id
            assert first.session_id != second.session_id
            assert first.session_title == "Sessão 12345678"
            assert second.session_title == "Sessão 87654321"
            assert first.session_type == second.session_type == "persistente"
            assert first.turn_count == active.turn_count == 3
            assert second.turn_count == closed.turn_count == 7
            assert tuple(view.query(SessionListItem)) == (first, second)
            assert view.query_one("#sessions-empty-state", Static).display is False
            list_sessions.assert_not_called()
            load_session.assert_not_called()
            persist_session.assert_not_called()
            resume_session.assert_not_called()

    asyncio.run(scenario())


def test_add_session_summary_skips_deleted() -> None:
    async def scenario() -> None:
        app = VillazApp()

        async with app.run_test(size=(160, 45)):
            view = SessionListView()
            await app.mount(view)
            deleted = make_summary(
                "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                lifecycle=SessionLifecycle.DELETED,
                turn_count=5,
            )

            assert await view.add_session_summary(deleted) is None
            assert tuple(view.query(SessionListItem)) == ()
            assert view.query_one("#sessions-empty-state", Static).display is True

    asyncio.run(scenario())


def test_session_item_lookup_does_not_change_selection() -> None:
    async def scenario() -> None:
        app = VillazApp()

        async with app.run_test(size=(160, 45)):
            view = SessionListView()
            await app.mount(view)
            first = await view.add_session_summary(
                make_summary("11111111-aaaa-bbbb-cccc-123456789abc")
            )
            second = await view.add_session_summary(
                make_summary("22222222-aaaa-bbbb-cccc-123456789abc")
            )

            assert first is not None
            assert second is not None
            view.select_session(first)

            assert view.get_session_item(first.session_id) is first
            assert view.get_session_item(second.session_id) is second
            assert view.get_session_item("missing-session-id") is None
            assert first.selected is True
            assert second.selected is False

            view.select_session(second)
            assert first.selected is False
            assert second.selected is True

    asyncio.run(scenario())


def test_set_session_summaries_replaces_items_in_received_order() -> None:
    async def scenario() -> None:
        app = VillazApp()

        with patch("villaz_cli.tui.app.list_persisted_sessions", return_value=()):
            async with app.run_test(size=(160, 45)):
                view = SessionListView()
                await app.mount(view)
                prior = await view.add_session(
                    session_id="previous-session",
                    title="Anterior",
                    session_type="persistente",
                    turn_count=1,
                    selected=True,
                )
                closed = make_summary(
                    "cccccccc-aaaa-bbbb-cccc-123456789abc",
                    lifecycle=SessionLifecycle.CLOSED,
                    turn_count=7,
                )
                deleted = make_summary(
                    "dddddddd-aaaa-bbbb-cccc-123456789abc",
                    lifecycle=SessionLifecycle.DELETED,
                )
                active = make_summary(
                    "aaaaaaaa-aaaa-bbbb-cccc-123456789abc",
                    turn_count=3,
                )

                with (
                    patch("villaz_cli.session_query.list_persisted_sessions") as query,
                    patch("villaz_cli.session_query.load_session") as load,
                    patch("villaz_cli.session_persistence.persist_session") as persist,
                ):
                    await view.set_session_summaries((closed, deleted, active))

                items = tuple(view.query(SessionListItem))
                assert prior not in items
                assert tuple(item.session_id for item in items) == (
                    closed.session_id,
                    active.session_id,
                )
                assert tuple(item.turn_count for item in items) == (7, 3)
                assert all(item.selected is False for item in items)
                assert all(item.has_class("selected") is False for item in items)
                assert view.query_one("#sessions-empty-state", Static).display is False
                query.assert_not_called()
                load.assert_not_called()
                persist.assert_not_called()

                await view.set_session_summaries(())
                assert tuple(view.query(SessionListItem)) == ()
                empty = view.query_one("#sessions-empty-state", Static)
                assert empty.display is True
                assert str(empty.render()) == "Nenhuma sessão\nselecionada"

    asyncio.run(scenario())


def test_session_load_error_is_sanitized_and_replaced_on_success() -> None:
    async def scenario() -> None:
        app = VillazApp()

        with patch("villaz_cli.tui.app.list_persisted_sessions", return_value=()):
            async with app.run_test(size=(160, 45)):
                view = SessionListView()
                await app.mount(view)
                await view.add_session_summary(
                    make_summary("secret-path-json-session")
                )

                await view.show_load_error()

                empty = view.query_one("#sessions-empty-state", Static)
                assert tuple(view.query(SessionListItem)) == ()
                assert empty.display is True
                assert str(empty.render()) == (
                    "Não foi possível carregar as sessões salvas."
                )
                assert "secret-path-json-session" not in str(empty.render())

                await view.set_session_summaries(
                    (make_summary("12345678-aaaa-bbbb-cccc-123456789abc"),)
                )

                assert tuple(view.query(SessionListItem))[0].session_id == (
                    "12345678-aaaa-bbbb-cccc-123456789abc"
                )
                assert empty.display is False
                assert str(empty.render()) == "Nenhuma sessão\nselecionada"

    asyncio.run(scenario())
