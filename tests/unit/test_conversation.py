import pytest

from villaz_cli.conversation import (
    ConversationResult,
    ConversationResultKind,
    EffectiveInferenceContext,
    LogicalConversationHistory,
    Message,
    MessageRole,
    Turn,
)


def _turn(
    user_content: str = "Olá",
    assistant_content: str = "Olá!",
) -> Turn:
    return Turn(
        user=Message(
            role=MessageRole.USER,
            content=user_content,
        ),
        assistant=Message(
            role=MessageRole.ASSISTANT,
            content=assistant_content,
        ),
    )


def test_message_preserves_role_and_content() -> None:
    message = Message(
        role=MessageRole.USER,
        content="Analise este código.",
    )

    assert message.role is MessageRole.USER
    assert message.content == "Analise este código."


def test_message_is_immutable() -> None:
    message = Message(
        role=MessageRole.USER,
        content="Olá",
    )

    with pytest.raises(AttributeError):
        message.content = "alterado"  # type: ignore[misc]


def test_turn_requires_user_role() -> None:
    with pytest.raises(
        ValueError,
        match="mensagem de usuário",
    ):
        Turn(
            user=Message(
                role=MessageRole.ASSISTANT,
                content="inválida",
            ),
            assistant=Message(
                role=MessageRole.ASSISTANT,
                content="resposta",
            ),
        )


def test_turn_requires_assistant_role() -> None:
    with pytest.raises(
        ValueError,
        match="mensagem do assistente",
    ):
        Turn(
            user=Message(
                role=MessageRole.USER,
                content="mensagem",
            ),
            assistant=Message(
                role=MessageRole.USER,
                content="inválida",
            ),
        )


def test_history_starts_empty() -> None:
    history = LogicalConversationHistory()

    assert history.turns == ()


def test_history_appends_complete_turns_in_order() -> None:
    history = LogicalConversationHistory()

    first = _turn("primeira", "resposta 1")
    second = _turn("segunda", "resposta 2")

    history.append(first)
    history.append(second)

    assert history.turns == (first, second)


def test_history_exposes_immutable_turn_collection() -> None:
    history = LogicalConversationHistory()
    history.append(_turn())

    turns = history.turns

    assert isinstance(turns, tuple)


def test_history_reset_removes_all_turns() -> None:
    history = LogicalConversationHistory()
    history.append(_turn("primeira", "resposta 1"))
    history.append(_turn("segunda", "resposta 2"))

    history.reset()

    assert history.turns == ()


def test_history_reset_is_idempotent_when_empty() -> None:
    history = LogicalConversationHistory()

    history.reset()

    assert history.turns == ()


def test_effective_context_from_empty_history() -> None:
    history = LogicalConversationHistory()

    context = EffectiveInferenceContext.from_history(
        history
    )

    assert context.turns == ()
    assert context.omitted_turn_count == 0
    assert context.is_truncated is False


def test_effective_context_preserves_history_order() -> None:
    history = LogicalConversationHistory()

    first = _turn(
        "primeira",
        "resposta 1",
    )
    second = _turn(
        "segunda",
        "resposta 2",
    )

    history.append(first)
    history.append(second)

    context = EffectiveInferenceContext.from_history(
        history
    )

    assert context.turns == (
        first,
        second,
    )
    assert context.omitted_turn_count == 0
    assert context.is_truncated is False


def test_effective_context_is_immutable() -> None:
    context = EffectiveInferenceContext(
        turns=(),
    )

    with pytest.raises(AttributeError):
        context.omitted_turn_count = 1  # type: ignore[misc]


def test_effective_context_is_snapshot_of_history() -> None:
    history = LogicalConversationHistory()

    first = _turn(
        "primeira",
        "resposta 1",
    )
    history.append(first)

    context = EffectiveInferenceContext.from_history(
        history
    )

    history.append(
        _turn(
            "segunda",
            "resposta 2",
        )
    )
    history.reset()

    assert context.turns == (first,)
    assert context.omitted_turn_count == 0


def test_effective_context_removes_oldest_complete_turn() -> None:
    history = LogicalConversationHistory()

    first = _turn(
        "primeira",
        "resposta 1",
    )
    second = _turn(
        "segunda",
        "resposta 2",
    )

    history.append(first)
    history.append(second)

    context = EffectiveInferenceContext.from_history(
        history
    )

    reduced = context.without_oldest_turn()

    assert reduced is not context
    assert context.turns == (
        first,
        second,
    )
    assert context.omitted_turn_count == 0

    assert reduced.turns == (second,)
    assert reduced.omitted_turn_count == 1
    assert reduced.is_truncated is True

    assert history.turns == (
        first,
        second,
    )


def test_effective_context_successive_reductions_preserve_order() -> None:
    history = LogicalConversationHistory()

    first = _turn(
        "primeira",
        "resposta 1",
    )
    second = _turn(
        "segunda",
        "resposta 2",
    )
    third = _turn(
        "terceira",
        "resposta 3",
    )

    history.append(first)
    history.append(second)
    history.append(third)

    initial = EffectiveInferenceContext.from_history(
        history
    )
    reduced_once = initial.without_oldest_turn()
    reduced_twice = reduced_once.without_oldest_turn()
    reduced_three_times = (
        reduced_twice.without_oldest_turn()
    )

    assert initial.turns == (
        first,
        second,
        third,
    )
    assert initial.omitted_turn_count == 0

    assert reduced_once.turns == (
        second,
        third,
    )
    assert reduced_once.omitted_turn_count == 1

    assert reduced_twice.turns == (third,)
    assert reduced_twice.omitted_turn_count == 2

    assert reduced_three_times.turns == ()
    assert reduced_three_times.omitted_turn_count == 3


def test_effective_context_empty_reduction_is_idempotent() -> None:
    context = EffectiveInferenceContext(
        turns=(),
        omitted_turn_count=3,
    )

    reduced = context.without_oldest_turn()

    assert reduced is context
    assert reduced.turns == ()
    assert reduced.omitted_turn_count == 3
    assert reduced.is_truncated is True


def test_new_effective_context_restarts_from_current_history() -> None:
    history = LogicalConversationHistory()

    first = _turn(
        "primeira",
        "resposta 1",
    )
    second = _turn(
        "segunda",
        "resposta 2",
    )

    history.append(first)
    history.append(second)

    original = EffectiveInferenceContext.from_history(
        history
    )
    truncated = original.without_oldest_turn()

    fresh = EffectiveInferenceContext.from_history(
        history
    )

    assert truncated.turns == (second,)
    assert truncated.omitted_turn_count == 1

    assert fresh.turns == (
        first,
        second,
    )
    assert fresh.omitted_turn_count == 0
    assert fresh.is_truncated is False


def test_effective_context_rejects_negative_omitted_count() -> None:
    with pytest.raises(
        ValueError,
        match="não pode ser negativo",
    ):
        EffectiveInferenceContext(
            turns=(),
            omitted_turn_count=-1,
        )


def test_conversation_result_success_preserves_assistant_message() -> None:
    assistant_message = Message(
        role=MessageRole.ASSISTANT,
        content="resposta semântica",
    )

    result = ConversationResult.success(
        assistant_message
    )

    assert result.kind is ConversationResultKind.SUCCESS
    assert result.assistant_message == assistant_message


def test_conversation_result_success_requires_assistant_message() -> None:
    with pytest.raises(
        ValueError,
        match="SUCCESS exige assistant_message",
    ):
        ConversationResult(
            kind=ConversationResultKind.SUCCESS,
        )


def test_conversation_result_success_rejects_user_message() -> None:
    with pytest.raises(
        ValueError,
        match="role 'assistant'",
    ):
        ConversationResult.success(
            Message(
                role=MessageRole.USER,
                content="mensagem de usuário",
            )
        )


def test_conversation_result_failure_has_no_assistant_message() -> None:
    result = ConversationResult.failure()

    assert result.kind is ConversationResultKind.FAILURE
    assert result.assistant_message is None


def test_conversation_result_failure_rejects_message() -> None:
    with pytest.raises(
        ValueError,
        match="FAILURE não pode possuir assistant_message",
    ):
        ConversationResult(
            kind=ConversationResultKind.FAILURE,
            assistant_message=Message(
                role=MessageRole.ASSISTANT,
                content="resposta",
            ),
        )


def test_conversation_result_is_immutable() -> None:
    result = ConversationResult.failure()

    with pytest.raises(AttributeError):
        result.kind = (  # type: ignore[misc]
            ConversationResultKind.SUCCESS
        )


def test_conversation_result_factories_use_expected_kinds() -> None:
    success = ConversationResult.success(
        Message(
            role=MessageRole.ASSISTANT,
            content="resposta",
        )
    )
    failure = ConversationResult.failure()

    assert success.kind is ConversationResultKind.SUCCESS
    assert failure.kind is ConversationResultKind.FAILURE
