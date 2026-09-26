from __future__ import annotations

from enum import StrEnum

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Static


class ConversationMessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class ConversationMessage(Vertical):
    """Pure presentation widget for one conversation message."""

    def __init__(
        self,
        *,
        role: ConversationMessageRole,
        content: str,
        timestamp: str | None = None,
        profile: str | None = None,
        elapsed_seconds: float | None = None,
        output_tokens: int | None = None,
    ) -> None:
        super().__init__()

        self.role = role
        self.content = content
        self.timestamp = timestamp
        self.profile = profile
        self.elapsed_seconds = elapsed_seconds
        self.output_tokens = output_tokens

        self.add_class("conversation-message")
        self.add_class(
            "user-message"
            if role is ConversationMessageRole.USER
            else "assistant-message"
        )

    def compose(self) -> ComposeResult:
        label = (
            "VOCÊ"
            if self.role is ConversationMessageRole.USER
            else "VILLAZ"
        )

        header = label

        if self.timestamp is not None:
            header = f"{header}    {self.timestamp}"

        yield Static(
            header,
            classes="message-header",
            markup=False,
        )

        yield Static(
            self.content,
            classes="message-content",
            markup=False,
        )

        metadata = self._metadata_text()

        if metadata is not None:
            yield Static(
                metadata,
                classes="message-metadata",
                markup=False,
            )

    def _metadata_text(self) -> str | None:
        parts: list[str] = []

        if self.profile is not None:
            parts.append(self.profile)

        if self.elapsed_seconds is not None:
            parts.append(
                f"{self.elapsed_seconds:.2f}s"
            )

        if self.output_tokens is not None:
            parts.append(
                f"{self.output_tokens} tokens"
            )

        if not parts:
            return None

        return "  •  ".join(parts)


class ConversationView(VerticalScroll):
    """Scrollable presentation surface for conversation messages."""

    can_focus = True

    def compose(self) -> ComposeResult:
        yield Static(
            "Inicie uma conversa para começar.",
            id="conversation-empty-state",
            markup=False,
        )

    async def append_message(
        self,
        message: ConversationMessage,
    ) -> None:
        empty_state = self.query_one(
            "#conversation-empty-state",
            Static,
        )

        empty_state.display = False

        await self.mount(
            message
        )

        self.scroll_end(
            animate=False,
        )

    async def append_user_message(
        self,
        content: str,
        *,
        timestamp: str | None = None,
    ) -> ConversationMessage:
        message = ConversationMessage(
            role=ConversationMessageRole.USER,
            content=content,
            timestamp=timestamp,
        )

        await self.append_message(
            message
        )

        return message

    async def append_assistant_message(
        self,
        content: str,
        *,
        timestamp: str | None = None,
        profile: str | None = None,
        elapsed_seconds: float | None = None,
        output_tokens: int | None = None,
    ) -> ConversationMessage:
        message = ConversationMessage(
            role=ConversationMessageRole.ASSISTANT,
            content=content,
            timestamp=timestamp,
            profile=profile,
            elapsed_seconds=elapsed_seconds,
            output_tokens=output_tokens,
        )

        await self.append_message(
            message
        )

        return message

    async def clear_messages(self) -> None:
        messages = tuple(
            self.query(
                ConversationMessage
            )
        )

        for message in messages:
            await message.remove()

        empty_state = self.query_one(
            "#conversation-empty-state",
            Static,
        )

        empty_state.display = True
