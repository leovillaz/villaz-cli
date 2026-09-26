import asyncio

from textual.widgets import Input, Static

from villaz_cli.session import (
    ProfileMode,
    ProfileModeKind,
)
from villaz_cli.tui.app import VillazApp
from villaz_cli.tui.profile import (
    ProfileSelectionScreen,
)


def test_profile_screen_auto_mode_starts_empty() -> None:
    async def scenario() -> None:
        app = VillazApp()

        async with app.run_test(
            size=(120, 40),
        ) as pilot:
            results: list[
                ProfileMode | None
            ] = []

            screen = ProfileSelectionScreen(
                current_mode=ProfileMode.auto()
            )

            app.push_screen(
                screen,
                results.append,
            )

            await pilot.pause()

            profile_input = screen.query_one(
                "#profile-input",
                Input,
            )

            current_mode = screen.query_one(
                "#profile-current-mode",
                Static,
            )

            validation = screen.query_one(
                "#profile-validation-message",
                Static,
            )

            assert (
                profile_input.value
                == ""
            )

            assert (
                "automático"
                in str(
                    current_mode.render()
                )
            )

            assert (
                validation.display
                is False
            )

            assert results == []

    asyncio.run(
        scenario()
    )


def test_profile_screen_explicit_mode_preloads_profile() -> None:
    async def scenario() -> None:
        app = VillazApp()

        async with app.run_test(
            size=(120, 40),
        ) as pilot:
            screen = ProfileSelectionScreen(
                current_mode=(
                    ProfileMode.explicit(
                        "code-review-security"
                    )
                )
            )

            app.push_screen(
                screen
            )

            await pilot.pause()

            profile_input = screen.query_one(
                "#profile-input",
                Input,
            )

            current_mode = screen.query_one(
                "#profile-current-mode",
                Static,
            )

            assert (
                profile_input.value
                == "code-review-security"
            )

            rendered = str(
                current_mode.render()
            )

            assert "explícito" in rendered
            assert (
                "code-review-security"
                in rendered
            )

    asyncio.run(
        scenario()
    )


def test_profile_screen_auto_button_returns_auto_mode() -> None:
    async def scenario() -> None:
        app = VillazApp()

        async with app.run_test(
            size=(120, 40),
        ) as pilot:
            results: list[
                ProfileMode | None
            ] = []

            app.push_screen(
                ProfileSelectionScreen(
                    current_mode=(
                        ProfileMode.explicit(
                            "unity-dev"
                        )
                    )
                ),
                results.append,
            )

            await pilot.pause()

            await pilot.click(
                "#profile-auto"
            )

            await pilot.pause()

            assert len(results) == 1

            result = results[0]

            assert result is not None
            assert (
                result.kind
                is ProfileModeKind.AUTO
            )
            assert (
                result.profile_id
                is None
            )

    asyncio.run(
        scenario()
    )


def test_profile_screen_apply_returns_trimmed_explicit_profile() -> None:
    async def scenario() -> None:
        app = VillazApp()

        async with app.run_test(
            size=(120, 40),
        ) as pilot:
            results: list[
                ProfileMode | None
            ] = []

            screen = ProfileSelectionScreen(
                current_mode=ProfileMode.auto()
            )

            app.push_screen(
                screen,
                results.append,
            )

            await pilot.pause()

            profile_input = screen.query_one(
                "#profile-input",
                Input,
            )

            profile_input.value = (
                "  code-review-security  "
            )

            await pilot.click(
                "#profile-apply"
            )

            await pilot.pause()

            assert results == [
                ProfileMode.explicit(
                    "code-review-security"
                )
            ]

    asyncio.run(
        scenario()
    )


def test_profile_screen_enter_applies_explicit_profile() -> None:
    async def scenario() -> None:
        app = VillazApp()

        async with app.run_test(
            size=(120, 40),
        ) as pilot:
            results: list[
                ProfileMode | None
            ] = []

            screen = ProfileSelectionScreen(
                current_mode=ProfileMode.auto()
            )

            app.push_screen(
                screen,
                results.append,
            )

            await pilot.pause()

            profile_input = screen.query_one(
                "#profile-input",
                Input,
            )

            profile_input.value = (
                "unity-dev"
            )
            profile_input.focus()

            await pilot.press(
                "enter"
            )

            await pilot.pause()

            assert results == [
                ProfileMode.explicit(
                    "unity-dev"
                )
            ]

    asyncio.run(
        scenario()
    )


def test_profile_screen_empty_explicit_profile_is_rejected() -> None:
    async def scenario() -> None:
        app = VillazApp()

        async with app.run_test(
            size=(120, 40),
        ) as pilot:
            results: list[
                ProfileMode | None
            ] = []

            screen = ProfileSelectionScreen(
                current_mode=ProfileMode.auto()
            )

            app.push_screen(
                screen,
                results.append,
            )

            await pilot.pause()

            profile_input = screen.query_one(
                "#profile-input",
                Input,
            )

            profile_input.value = "   "

            await pilot.click(
                "#profile-apply"
            )

            await pilot.pause()

            validation = screen.query_one(
                "#profile-validation-message",
                Static,
            )

            assert results == []
            assert (
                app.screen
                is screen
            )
            assert (
                validation.display
                is True
            )

            assert (
                str(validation.render())
                == (
                    "Informe um profile ou "
                    "escolha Automático."
                )
            )

    asyncio.run(
        scenario()
    )


def test_profile_screen_cancel_button_returns_none() -> None:
    async def scenario() -> None:
        app = VillazApp()

        async with app.run_test(
            size=(120, 40),
        ) as pilot:
            results: list[
                ProfileMode | None
            ] = []

            app.push_screen(
                ProfileSelectionScreen(
                    current_mode=(
                        ProfileMode.auto()
                    )
                ),
                results.append,
            )

            await pilot.pause()

            await pilot.click(
                "#profile-cancel"
            )

            await pilot.pause()

            assert results == [None]

    asyncio.run(
        scenario()
    )


def test_profile_screen_escape_returns_none() -> None:
    async def scenario() -> None:
        app = VillazApp()

        async with app.run_test(
            size=(120, 40),
        ) as pilot:
            results: list[
                ProfileMode | None
            ] = []

            app.push_screen(
                ProfileSelectionScreen(
                    current_mode=(
                        ProfileMode.auto()
                    )
                ),
                results.append,
            )

            await pilot.pause()

            await pilot.press(
                "escape"
            )

            await pilot.pause()

            assert results == [None]

    asyncio.run(
        scenario()
    )
