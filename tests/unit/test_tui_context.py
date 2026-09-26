import asyncio

from textual.widgets import Static

from villaz_cli.tui.app import VillazApp
from villaz_cli.tui.context import ContextView


def test_context_view_uses_known_initial_values() -> None:
    async def scenario() -> None:
        app = VillazApp()

        async with app.run_test(
            size=(160, 45),
        ):
            view = ContextView()

            await app.mount(
                view
            )

            assert view.mode == "auto"
            assert view.session_type == "efêmera"
            assert view.turn_count == 0
            assert view.profile is None

    asyncio.run(
        scenario()
    )


def test_context_renders_initial_values() -> None:
    async def scenario() -> None:
        app = VillazApp()

        async with app.run_test(
            size=(160, 45),
        ):
            view = ContextView()

            await app.mount(
                view
            )

            mode = view.query_one(
                "#context-mode",
                Static,
            )

            session = view.query_one(
                "#context-session",
                Static,
            )

            turns = view.query_one(
                "#context-turns",
                Static,
            )

            assert "auto" in str(
                mode.render()
            )

            assert "efêmera" in str(
                session.render()
            )

            assert "0" in str(
                turns.render()
            )

    asyncio.run(
        scenario()
    )


def test_context_updates_mode() -> None:
    async def scenario() -> None:
        app = VillazApp()

        async with app.run_test(
            size=(160, 45),
        ):
            view = ContextView()

            await app.mount(
                view
            )

            view.set_mode(
                "explícito"
            )

            rendered = str(
                view.query_one(
                    "#context-mode",
                    Static,
                ).render()
            )

            assert "explícito" in rendered

    asyncio.run(
        scenario()
    )


def test_context_updates_session_type_and_turn_count() -> None:
    async def scenario() -> None:
        app = VillazApp()

        async with app.run_test(
            size=(160, 45),
        ):
            view = ContextView()

            await app.mount(
                view
            )

            view.set_session_type(
                "persistente"
            )

            view.set_turn_count(
                12
            )

            session = str(
                view.query_one(
                    "#context-session",
                    Static,
                ).render()
            )

            turns = str(
                view.query_one(
                    "#context-turns",
                    Static,
                ).render()
            )

            assert "persistente" in session
            assert "12" in turns

    asyncio.run(
        scenario()
    )


def test_context_profile_is_hidden_when_absent() -> None:
    async def scenario() -> None:
        app = VillazApp()

        async with app.run_test(
            size=(160, 45),
        ):
            view = ContextView()

            await app.mount(
                view
            )

            profile = view.query_one(
                "#context-profile",
                Static,
            )

            assert profile.display is False

    asyncio.run(
        scenario()
    )


def test_context_profile_appears_when_provided() -> None:
    async def scenario() -> None:
        app = VillazApp()

        async with app.run_test(
            size=(160, 45),
        ):
            view = ContextView()

            await app.mount(
                view
            )

            view.set_profile(
                "unity-dev"
            )

            profile = view.query_one(
                "#context-profile",
                Static,
            )

            assert profile.display is True
            assert "unity-dev" in str(
                profile.render()
            )

    asyncio.run(
        scenario()
    )


def test_context_profile_can_be_removed_again() -> None:
    async def scenario() -> None:
        app = VillazApp()

        async with app.run_test(
            size=(160, 45),
        ):
            view = ContextView(
                profile="unity-dev"
            )

            await app.mount(
                view
            )

            view.set_profile(
                None
            )

            profile = view.query_one(
                "#context-profile",
                Static,
            )

            assert profile.display is False
            assert str(
                profile.render()
            ) == ""

    asyncio.run(
        scenario()
    )
