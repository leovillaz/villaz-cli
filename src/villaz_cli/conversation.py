from dataclasses import dataclass
from enum import StrEnum


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class ConversationResultKind(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"


@dataclass(frozen=True, slots=True)
class Message:
    role: MessageRole
    content: str


@dataclass(frozen=True, slots=True)
class ConversationResult:
    kind: ConversationResultKind
    assistant_message: Message | None = None

    def __post_init__(self) -> None:
        if self.kind is ConversationResultKind.SUCCESS:
            if self.assistant_message is None:
                raise ValueError(
                    "ConversationResult SUCCESS exige assistant_message."
                )

            if (
                self.assistant_message.role
                is not MessageRole.ASSISTANT
            ):
                raise ValueError(
                    "assistant_message deve possuir role 'assistant'."
                )

            return

        if self.assistant_message is not None:
            raise ValueError(
                "ConversationResult FAILURE não pode possuir "
                "assistant_message."
            )

    @classmethod
    def success(
        cls,
        assistant_message: Message,
    ) -> "ConversationResult":
        return cls(
            kind=ConversationResultKind.SUCCESS,
            assistant_message=assistant_message,
        )

    @classmethod
    def failure(cls) -> "ConversationResult":
        return cls(
            kind=ConversationResultKind.FAILURE,
        )


@dataclass(frozen=True, slots=True)
class Turn:
    user: Message
    assistant: Message

    def __post_init__(self) -> None:
        if self.user.role is not MessageRole.USER:
            raise ValueError("A mensagem de usuário deve possuir role 'user'.")

        if self.assistant.role is not MessageRole.ASSISTANT:
            raise ValueError(
                "A mensagem do assistente deve possuir role 'assistant'."
            )


class LogicalConversationHistory:
    def __init__(self) -> None:
        self._turns: list[Turn] = []

    @property
    def turns(self) -> tuple[Turn, ...]:
        return tuple(self._turns)

    def append(self, turn: Turn) -> None:
        self._turns.append(turn)

    def reset(self) -> None:
        self._turns.clear()


@dataclass(frozen=True, slots=True)
class EffectiveInferenceContext:
    turns: tuple[Turn, ...]
    omitted_turn_count: int = 0

    def __post_init__(self) -> None:
        if self.omitted_turn_count < 0:
            raise ValueError(
                "omitted_turn_count não pode ser negativo."
            )

    @classmethod
    def from_history(
        cls,
        history: LogicalConversationHistory,
    ) -> "EffectiveInferenceContext":
        return cls(
            turns=history.turns,
        )

    @property
    def is_truncated(self) -> bool:
        return self.omitted_turn_count > 0

    def without_oldest_turn(
        self,
    ) -> "EffectiveInferenceContext":
        if not self.turns:
            return self

        return EffectiveInferenceContext(
            turns=self.turns[1:],
            omitted_turn_count=(
                self.omitted_turn_count + 1
            ),
        )
