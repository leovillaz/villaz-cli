import json

import httpx
import pytest

from datetime import datetime, timezone
from typing import Any

from villaz_cli.conversation import (
    EffectiveInferenceContext,
    LogicalConversationHistory,
    Message,
    MessageRole,
    Turn,
)
from villaz_cli.conversation_execution import (
    ConversationExecutionResult,
    SessionMessageExecutionResult,
    execute_session_message,
    execute_conversation_request,
    to_conversation_result,
)
from villaz_cli.http_client import (
    PromptResult,
    RouterAPIError,
)
from villaz_cli.session import (
    ConversationRequest,
    PersistenceMode,
    ProfileMode,
    Session,
    SessionAuthority,
    SessionLifecycle,
    SessionSyncState,
)
from villaz_cli.session_persistence import (
    SessionStorageError,
)


def _turn(
    user: str,
    assistant: str,
) -> Turn:
    return Turn(
        user=Message(
            role=MessageRole.USER,
            content=user,
        ),
        assistant=Message(
            role=MessageRole.ASSISTANT,
            content=assistant,
        ),
    )


def _request(
    *,
    turns: tuple[Turn, ...] = (),
    profile_mode: ProfileMode | None = None,
    current_message: str = "mensagem atual",
) -> ConversationRequest:
    return ConversationRequest(
        current_message=Message(
            role=MessageRole.USER,
            content=current_message,
        ),
        effective_context=EffectiveInferenceContext(
            turns=turns,
        ),
        profile_mode=(
            profile_mode
            if profile_mode is not None
            else ProfileMode.auto()
        ),
    )


def _success_response() -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "response": "Resposta final.",
            "profile": "unity-dev",
            "model": "qwen2.5-coder:14b",
            "state": "routed",
            "route_id": "ROUTE-UNITY-001",
            "metrics": {
                "output_tokens": 20,
                "generation_duration_ns": (
                    1_000_000_000
                ),
                "tokens_per_second": 20.0,
            },
        },
    )


def _overflow_response() -> httpx.Response:
    return httpx.Response(
        422,
        json={
            "error": {
                "code": "CONTEXT_OVERFLOW",
                "message": (
                    "The request exceeds the "
                    "available model context."
                ),
            }
        },
    )


_SESSION_CREATED_AT = datetime(
    2026,
    9,
    13,
    17,
    0,
    tzinfo=timezone.utc,
)

_SESSION_UPDATED_AT = datetime(
    2026,
    9,
    13,
    17,
    30,
    tzinfo=timezone.utc,
)


class SessionExecutionStateStore:
    def __init__(self) -> None:
        self.states: dict[str, dict[str, Any]] = {}
        self.save_calls = 0
        self.fail_save = False

    def save(
        self,
        *,
        session_id: str,
        state: dict[str, Any],
    ) -> None:
        self.save_calls += 1

        if self.fail_save:
            raise SessionStorageError(
                "Falha simulada ao salvar Session."
            )

        self.states[session_id] = state

    def load(
        self,
        *,
        session_id: str,
    ) -> dict[str, Any]:
        return self.states[session_id]

    def list_session_ids(self) -> tuple[str, ...]:
        return tuple(
            sorted(self.states)
        )

    def purge(
        self,
        *,
        session_id: str,
    ) -> None:
        del self.states[session_id]


def _execution_session(
    *,
    persistence_mode: PersistenceMode = PersistenceMode.EPHEMERAL,
    profile_mode: ProfileMode | None = None,
) -> Session:
    return Session(
        session_id="session-execution",
        conversation=LogicalConversationHistory(),
        persistence_mode=persistence_mode,
        authority=SessionAuthority.LOCAL,
        profile_mode=profile_mode or ProfileMode.auto(),
        created_at=_SESSION_CREATED_AT,
        updated_at=_SESSION_CREATED_AT,
        lifecycle=SessionLifecycle.ACTIVE,
        sync_state=SessionSyncState.CLEAN,
    )


def test_success_on_first_attempt_uses_one_request() -> None:
    request_count = 0

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        nonlocal request_count
        request_count += 1

        return _success_response()

    result = execute_conversation_request(
        _request(),
        transport=httpx.MockTransport(
            handler
        ),
    )

    assert request_count == 1
    assert isinstance(
        result,
        ConversationExecutionResult,
    )
    assert result.prompt_result == PromptResult(
        response="Resposta final.",
        profile="unity-dev",
        model="qwen2.5-coder:14b",
        state="routed",
        route_id="ROUTE-UNITY-001",
        output_tokens=20,
        generation_duration_ns=(
            1_000_000_000
        ),
        tokens_per_second=20.0,
    )
    assert result.effective_context.turns == ()
    assert (
        result.effective_context
        .omitted_turn_count
        == 0
    )


@pytest.mark.parametrize(
    "error_code",
    [
        "UNROUTED",
        "AMBIGUOUS",
        "INVALID_PROFILE",
        "HTTP_STATUS_ERROR",
    ],
)
def test_non_context_overflow_error_is_not_retried(
    error_code: str,
) -> None:
    request_count = 0

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        nonlocal request_count
        request_count += 1

        return httpx.Response(
            422,
            json={
                "error": {
                    "code": error_code,
                    "message": "erro",
                }
            },
        )

    with pytest.raises(
        RouterAPIError
    ) as exc_info:
        execute_conversation_request(
            _request(
                turns=(
                    _turn(
                        "primeira",
                        "resposta 1",
                    ),
                ),
            ),
            transport=httpx.MockTransport(
                handler
            ),
        )

    assert exc_info.value.code == error_code
    assert request_count == 1


def test_context_overflow_removes_only_oldest_complete_turn() -> None:
    first = _turn(
        "primeira",
        "resposta 1",
    )
    second = _turn(
        "segunda",
        "resposta 2",
    )

    payloads: list[dict[str, object]] = []

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        payloads.append(
            json.loads(request.content)
        )

        if len(payloads) == 1:
            return _overflow_response()

        return _success_response()

    result = execute_conversation_request(
        _request(
            turns=(
                first,
                second,
            ),
        ),
        transport=httpx.MockTransport(
            handler
        ),
    )

    assert payloads == [
        {
            "message": "mensagem atual",
            "history": [
                {
                    "user": "primeira",
                    "assistant": "resposta 1",
                },
                {
                    "user": "segunda",
                    "assistant": "resposta 2",
                },
            ],
        },
        {
            "message": "mensagem atual",
            "history": [
                {
                    "user": "segunda",
                    "assistant": "resposta 2",
                }
            ],
        },
    ]

    assert result.effective_context.turns == (
        second,
    )
    assert (
        result.effective_context
        .omitted_turn_count
        == 1
    )


def test_multiple_overflows_remove_one_turn_per_retry() -> None:
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

    histories: list[
        list[dict[str, str]]
    ] = []

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        payload = json.loads(
            request.content
        )

        histories.append(
            payload["history"]
        )

        if len(histories) < 3:
            return _overflow_response()

        return _success_response()

    result = execute_conversation_request(
        _request(
            turns=(
                first,
                second,
                third,
            ),
        ),
        transport=httpx.MockTransport(
            handler
        ),
    )

    assert histories == [
        [
            {
                "user": "primeira",
                "assistant": "resposta 1",
            },
            {
                "user": "segunda",
                "assistant": "resposta 2",
            },
            {
                "user": "terceira",
                "assistant": "resposta 3",
            },
        ],
        [
            {
                "user": "segunda",
                "assistant": "resposta 2",
            },
            {
                "user": "terceira",
                "assistant": "resposta 3",
            },
        ],
        [
            {
                "user": "terceira",
                "assistant": "resposta 3",
            }
        ],
    ]

    assert result.effective_context.turns == (
        third,
    )
    assert (
        result.effective_context
        .omitted_turn_count
        == 2
    )


def test_success_result_returns_effective_context_that_succeeded() -> None:
    first = _turn(
        "primeira",
        "resposta 1",
    )
    second = _turn(
        "segunda",
        "resposta 2",
    )

    request_count = 0

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        nonlocal request_count
        request_count += 1

        if request_count == 1:
            return _overflow_response()

        return _success_response()

    result = execute_conversation_request(
        _request(
            turns=(
                first,
                second,
            ),
        ),
        transport=httpx.MockTransport(
            handler
        ),
    )

    assert result.effective_context.turns == (
        second,
    )
    assert (
        result.effective_context
        .omitted_turn_count
        == 1
    )


def test_current_message_is_preserved_across_retries() -> None:
    seen_messages: list[str] = []
    original_message = (
        "  mensagem atual\ncom espaços  "
    )

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        payload = json.loads(
            request.content
        )
        seen_messages.append(
            payload["message"]
        )

        if len(seen_messages) == 1:
            return _overflow_response()

        return _success_response()

    execute_conversation_request(
        _request(
            turns=(
                _turn(
                    "anterior",
                    "resposta",
                ),
            ),
            current_message=original_message,
        ),
        transport=httpx.MockTransport(
            handler
        ),
    )

    assert seen_messages == [
        original_message,
        original_message,
    ]


def test_explicit_profile_is_preserved_across_retries() -> None:
    seen_profiles: list[str] = []

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        payload = json.loads(
            request.content
        )

        seen_profiles.append(
            payload["explicit_profile"]
        )

        if len(seen_profiles) == 1:
            return _overflow_response()

        return _success_response()

    execute_conversation_request(
        _request(
            turns=(
                _turn(
                    "anterior",
                    "resposta",
                ),
            ),
            profile_mode=(
                ProfileMode.explicit(
                    "  unity-dev  "
                )
            ),
        ),
        transport=httpx.MockTransport(
            handler
        ),
    )

    assert seen_profiles == [
        "  unity-dev  ",
        "  unity-dev  ",
    ]


def test_remaining_turn_order_and_content_are_preserved() -> None:
    first = _turn(
        "primeira",
        "resposta 1",
    )
    second = _turn(
        "  segunda\n",
        " resposta 2  ",
    )
    third = _turn(
        "terceira\t",
        "resposta 3\n",
    )

    successful_payload: dict[
        str,
        object,
    ] | None = None

    request_count = 0

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        nonlocal request_count
        nonlocal successful_payload

        request_count += 1

        if request_count == 1:
            return _overflow_response()

        successful_payload = json.loads(
            request.content
        )

        return _success_response()

    execute_conversation_request(
        _request(
            turns=(
                first,
                second,
                third,
            ),
        ),
        transport=httpx.MockTransport(
            handler
        ),
    )

    assert successful_payload is not None

    assert successful_payload["history"] == [
        {
            "user": "  segunda\n",
            "assistant": " resposta 2  ",
        },
        {
            "user": "terceira\t",
            "assistant": "resposta 3\n",
        },
    ]


def test_original_request_is_not_mutated() -> None:
    first = _turn(
        "primeira",
        "resposta 1",
    )
    second = _turn(
        "segunda",
        "resposta 2",
    )

    original_request = _request(
        turns=(
            first,
            second,
        ),
        profile_mode=(
            ProfileMode.explicit(
                "unity-dev"
            )
        ),
    )

    original_message = (
        original_request.current_message
    )
    original_context = (
        original_request.effective_context
    )
    original_profile = (
        original_request.profile_mode
    )

    request_count = 0

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        nonlocal request_count
        request_count += 1

        if request_count == 1:
            return _overflow_response()

        return _success_response()

    execute_conversation_request(
        original_request,
        transport=httpx.MockTransport(
            handler
        ),
    )

    assert (
        original_request.current_message
        is original_message
    )
    assert (
        original_request.effective_context
        is original_context
    )
    assert (
        original_request.profile_mode
        is original_profile
    )

    assert original_request.effective_context.turns == (
        first,
        second,
    )
    assert (
        original_request
        .effective_context
        .omitted_turn_count
        == 0
    )


def test_context_overflow_with_empty_context_is_propagated_without_retry() -> None:
    request_count = 0

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        nonlocal request_count
        request_count += 1

        return _overflow_response()

    with pytest.raises(
        RouterAPIError
    ) as exc_info:
        execute_conversation_request(
            _request(),
            transport=httpx.MockTransport(
                handler
            ),
        )

    assert (
        exc_info.value.code
        == "CONTEXT_OVERFLOW"
    )
    assert request_count == 1


def test_maximum_request_count_is_turn_count_plus_one() -> None:
    turns = (
        _turn(
            "primeira",
            "resposta 1",
        ),
        _turn(
            "segunda",
            "resposta 2",
        ),
        _turn(
            "terceira",
            "resposta 3",
        ),
    )

    request_count = 0

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        nonlocal request_count
        request_count += 1

        return _overflow_response()

    with pytest.raises(
        RouterAPIError
    ) as exc_info:
        execute_conversation_request(
            _request(
                turns=turns,
            ),
            transport=httpx.MockTransport(
                handler
            ),
        )

    assert (
        exc_info.value.code
        == "CONTEXT_OVERFLOW"
    )
    assert request_count == len(turns) + 1


def test_retry_does_not_mutate_logical_history_source_objects() -> None:
    first = _turn(
        "primeira",
        "resposta 1",
    )
    second = _turn(
        "segunda",
        "resposta 2",
    )

    original_turns = (
        first,
        second,
    )

    request_count = 0

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        nonlocal request_count
        request_count += 1

        if request_count == 1:
            return _overflow_response()

        return _success_response()

    execute_conversation_request(
        _request(
            turns=original_turns,
        ),
        transport=httpx.MockTransport(
            handler
        ),
    )

    assert original_turns == (
        first,
        second,
    )
    assert original_turns[0] is first
    assert original_turns[1] is second


def test_to_conversation_result_returns_success() -> None:
    execution_result = ConversationExecutionResult(
        prompt_result=PromptResult(
            response="Resposta final.",
            profile="unity-dev",
            model="qwen2.5-coder:14b",
            state="routed",
            route_id="ROUTE-UNITY-001",
            output_tokens=20,
            generation_duration_ns=(
                1_000_000_000
            ),
            tokens_per_second=20.0,
        ),
        effective_context=(
            EffectiveInferenceContext(
                turns=(),
            )
        ),
    )

    result = to_conversation_result(
        execution_result
    )

    assert (
        result.kind.value
        == "success"
    )
    assert result.assistant_message is not None


def test_to_conversation_result_creates_assistant_message() -> None:
    execution_result = ConversationExecutionResult(
        prompt_result=PromptResult(
            response="Resposta.",
            profile="unity-dev",
            model="qwen2.5-coder:14b",
            state="routed",
            route_id="ROUTE-UNITY-001",
            output_tokens=1,
            generation_duration_ns=1,
            tokens_per_second=1.0,
        ),
        effective_context=(
            EffectiveInferenceContext(
                turns=(),
            )
        ),
    )

    result = to_conversation_result(
        execution_result
    )

    assert result.assistant_message is not None
    assert (
        result.assistant_message.role
        is MessageRole.ASSISTANT
    )


def test_to_conversation_result_preserves_response_content_exactly() -> None:
    response = (
        "  resposta\n"
        "com\twhitespace  "
    )

    execution_result = ConversationExecutionResult(
        prompt_result=PromptResult(
            response=response,
            profile="unity-dev",
            model="qwen2.5-coder:14b",
            state="routed",
            route_id="ROUTE-UNITY-001",
            output_tokens=10,
            generation_duration_ns=10,
            tokens_per_second=1.0,
        ),
        effective_context=(
            EffectiveInferenceContext(
                turns=(),
            )
        ),
    )

    result = to_conversation_result(
        execution_result
    )

    assert result.assistant_message is not None
    assert (
        result.assistant_message.content
        == response
    )


def test_to_conversation_result_does_not_expose_http_metadata() -> None:
    execution_result = ConversationExecutionResult(
        prompt_result=PromptResult(
            response="Resposta.",
            profile="unity-dev",
            model="modelo-interno",
            state="routed",
            route_id="ROTA-INTERNA",
            output_tokens=123,
            generation_duration_ns=456,
            tokens_per_second=7.5,
        ),
        effective_context=(
            EffectiveInferenceContext(
                turns=(),
            )
        ),
    )

    result = to_conversation_result(
        execution_result
    )

    assert result.assistant_message is not None

    assert (
        result.assistant_message.content
        == "Resposta."
    )

    assert not hasattr(
        result,
        "profile",
    )
    assert not hasattr(
        result,
        "model",
    )
    assert not hasattr(
        result,
        "state",
    )
    assert not hasattr(
        result,
        "route_id",
    )
    assert not hasattr(
        result,
        "metrics",
    )


def test_to_conversation_result_does_not_mutate_execution_result() -> None:
    context = EffectiveInferenceContext(
        turns=(
            _turn(
                "anterior",
                "resposta anterior",
            ),
        ),
        omitted_turn_count=2,
    )

    prompt_result = PromptResult(
        response="Resposta nova.",
        profile="unity-dev",
        model="qwen2.5-coder:14b",
        state="routed",
        route_id="ROUTE-UNITY-001",
        output_tokens=20,
        generation_duration_ns=100,
        tokens_per_second=2.0,
    )

    execution_result = ConversationExecutionResult(
        prompt_result=prompt_result,
        effective_context=context,
    )

    to_conversation_result(
        execution_result
    )

    assert (
        execution_result.prompt_result
        is prompt_result
    )
    assert (
        execution_result.effective_context
        is context
    )
    assert (
        execution_result
        .effective_context
        .omitted_turn_count
        == 2
    )
    assert (
        execution_result
        .effective_context
        .turns
        == context.turns
    )


def test_to_conversation_result_does_not_change_effective_context() -> None:
    turn = _turn(
        "pergunta anterior",
        "resposta anterior",
    )

    context = EffectiveInferenceContext(
        turns=(turn,),
        omitted_turn_count=3,
    )

    execution_result = ConversationExecutionResult(
        prompt_result=PromptResult(
            response="Resposta nova.",
            profile="unity-dev",
            model="qwen2.5-coder:14b",
            state="routed",
            route_id="ROUTE-UNITY-001",
            output_tokens=10,
            generation_duration_ns=100,
            tokens_per_second=1.0,
        ),
        effective_context=context,
    )

    to_conversation_result(
        execution_result
    )

    assert (
        execution_result.effective_context
        is context
    )
    assert (
        execution_result.effective_context.turns
        == (turn,)
    )
    assert (
        execution_result
        .effective_context
        .omitted_turn_count
        == 3
    )


def test_to_conversation_result_requires_no_http_execution() -> None:
    execution_result = ConversationExecutionResult(
        prompt_result=PromptResult(
            response="Resposta local.",
            profile="unity-dev",
            model="qwen2.5-coder:14b",
            state="routed",
            route_id=None,
            output_tokens=1,
            generation_duration_ns=1,
            tokens_per_second=1.0,
        ),
        effective_context=(
            EffectiveInferenceContext(
                turns=(),
            )
        ),
    )

    result = to_conversation_result(
        execution_result
    )

    assert result.assistant_message is not None
    assert (
        result.assistant_message.content
        == "Resposta local."
    )


def test_execute_session_message_confirms_ephemeral_turn_without_save(
    monkeypatch,
) -> None:
    store = SessionExecutionStateStore()
    session = _execution_session()

    current_message = Message(
        role=MessageRole.USER,
        content="mensagem atual",
    )

    prompt_result = PromptResult(
        response="resposta atual",
        profile="general",
        model="model-test",
        state="routed",
        route_id="route-test",
        output_tokens=10,
        generation_duration_ns=1_000_000,
        tokens_per_second=10.0,
    )

    captured_requests: list[ConversationRequest] = []

    def fake_execute(
        request: ConversationRequest,
        **kwargs,
    ) -> ConversationExecutionResult:
        del kwargs
        captured_requests.append(request)

        return ConversationExecutionResult(
            prompt_result=prompt_result,
            effective_context=request.effective_context,
        )

    monkeypatch.setattr(
        "villaz_cli.conversation_execution.execute_conversation_request",
        fake_execute,
    )

    result = execute_session_message(
        session,
        current_message,
        updated_at=_SESSION_UPDATED_AT,
        store=store,
    )

    assert isinstance(
        result,
        SessionMessageExecutionResult,
    )
    assert len(captured_requests) == 1
    assert captured_requests[0].current_message is current_message
    assert result.prompt_result is prompt_result
    assert result.turn.user is current_message
    assert result.turn.assistant.content == "resposta atual"
    assert session.conversation.turns == (
        result.turn,
    )
    assert session.updated_at == _SESSION_UPDATED_AT
    assert session.sync_state is SessionSyncState.CLEAN
    assert store.save_calls == 0


def test_execute_session_message_uses_session_profile_mode(
    monkeypatch,
) -> None:
    store = SessionExecutionStateStore()

    profile_mode = ProfileMode.explicit(
        "code-review-security"
    )

    session = _execution_session(
        profile_mode=profile_mode,
    )

    captured: list[ConversationRequest] = []

    def fake_execute(
        request: ConversationRequest,
        **kwargs,
    ) -> ConversationExecutionResult:
        del kwargs
        captured.append(request)

        return ConversationExecutionResult(
            prompt_result=PromptResult(
                response="resposta",
                profile="code-review-security",
                model="model-test",
                state="explicit",
                route_id=None,
                output_tokens=10,
                generation_duration_ns=1_000_000,
                tokens_per_second=10.0,
            ),
            effective_context=request.effective_context,
        )

    monkeypatch.setattr(
        "villaz_cli.conversation_execution.execute_conversation_request",
        fake_execute,
    )

    execute_session_message(
        session,
        Message(
            role=MessageRole.USER,
            content="revise este código",
        ),
        updated_at=_SESSION_UPDATED_AT,
        store=store,
    )

    assert captured[0].profile_mode is profile_mode
    assert captured[0].profile_mode.profile_id == (
        "code-review-security"
    )


def test_execute_session_message_returns_actual_effective_context_without_replacing_history(
    monkeypatch,
) -> None:
    store = SessionExecutionStateStore()
    session = _execution_session()

    first = Turn(
        user=Message(
            role=MessageRole.USER,
            content="primeira",
        ),
        assistant=Message(
            role=MessageRole.ASSISTANT,
            content="resposta 1",
        ),
    )
    second = Turn(
        user=Message(
            role=MessageRole.USER,
            content="segunda",
        ),
        assistant=Message(
            role=MessageRole.ASSISTANT,
            content="resposta 2",
        ),
    )

    session.conversation.append(first)
    session.conversation.append(second)

    reduced_context = EffectiveInferenceContext(
        turns=(second,),
        omitted_turn_count=1,
    )

    def fake_execute(
        request: ConversationRequest,
        **kwargs,
    ) -> ConversationExecutionResult:
        del request
        del kwargs

        return ConversationExecutionResult(
            prompt_result=PromptResult(
                response="resposta 3",
                profile="general",
                model="model-test",
                state="routed",
                route_id="route-test",
                output_tokens=10,
                generation_duration_ns=1_000_000,
                tokens_per_second=10.0,
            ),
            effective_context=reduced_context,
        )

    monkeypatch.setattr(
        "villaz_cli.conversation_execution.execute_conversation_request",
        fake_execute,
    )

    result = execute_session_message(
        session,
        Message(
            role=MessageRole.USER,
            content="terceira",
        ),
        updated_at=_SESSION_UPDATED_AT,
        store=store,
    )

    assert result.effective_context is reduced_context
    assert result.effective_context.omitted_turn_count == 1
    assert session.conversation.turns == (
        first,
        second,
        result.turn,
    )


def test_execute_session_message_propagates_router_error_without_mutating_session(
    monkeypatch,
) -> None:
    store = SessionExecutionStateStore()
    session = _execution_session()

    original_turns = session.conversation.turns
    original_updated_at = session.updated_at

    def fail_execute(
        request: ConversationRequest,
        **kwargs,
    ) -> ConversationExecutionResult:
        del request
        del kwargs

        raise RouterAPIError(
            code="UNROUTED",
            message="The request could not be routed.",
        )

    monkeypatch.setattr(
        "villaz_cli.conversation_execution.execute_conversation_request",
        fail_execute,
    )

    with pytest.raises(
        RouterAPIError,
    ):
        execute_session_message(
            session,
            Message(
                role=MessageRole.USER,
                content="mensagem",
            ),
            updated_at=_SESSION_UPDATED_AT,
            store=store,
        )

    assert session.conversation.turns == original_turns
    assert session.updated_at == original_updated_at
    assert store.save_calls == 0


def test_execute_session_message_persistence_failure_keeps_turn_and_dirty_state(
    monkeypatch,
) -> None:
    store = SessionExecutionStateStore()
    store.fail_save = True

    session = _execution_session(
        persistence_mode=PersistenceMode.PERSISTENT,
    )

    prompt_result = PromptResult(
        response="resposta válida",
        profile="general",
        model="model-test",
        state="routed",
        route_id="route-test",
        output_tokens=10,
        generation_duration_ns=1_000_000,
        tokens_per_second=10.0,
    )

    def fake_execute(
        request: ConversationRequest,
        **kwargs,
    ) -> ConversationExecutionResult:
        del kwargs

        return ConversationExecutionResult(
            prompt_result=prompt_result,
            effective_context=request.effective_context,
        )

    monkeypatch.setattr(
        "villaz_cli.conversation_execution.execute_conversation_request",
        fake_execute,
    )

    with pytest.raises(
        SessionStorageError,
        match="salvar",
    ):
        execute_session_message(
            session,
            Message(
                role=MessageRole.USER,
                content="pergunta",
            ),
            updated_at=_SESSION_UPDATED_AT,
            store=store,
        )

    assert len(session.conversation.turns) == 1
    assert (
        session.conversation.turns[0]
        .assistant.content
        == "resposta válida"
    )
    assert session.sync_state is SessionSyncState.DIRTY
    assert store.save_calls == 1


def test_execute_session_message_persistent_success_autosaves_and_returns_clean(
    monkeypatch,
) -> None:
    store = SessionExecutionStateStore()

    session = _execution_session(
        persistence_mode=PersistenceMode.PERSISTENT,
    )

    def fake_execute(
        request: ConversationRequest,
        **kwargs,
    ) -> ConversationExecutionResult:
        del kwargs

        return ConversationExecutionResult(
            prompt_result=PromptResult(
                response="persistida",
                profile="general",
                model="model-test",
                state="routed",
                route_id="route-test",
                output_tokens=10,
                generation_duration_ns=1_000_000,
                tokens_per_second=10.0,
            ),
            effective_context=request.effective_context,
        )

    monkeypatch.setattr(
        "villaz_cli.conversation_execution.execute_conversation_request",
        fake_execute,
    )

    result = execute_session_message(
        session,
        Message(
            role=MessageRole.USER,
            content="mensagem persistente",
        ),
        updated_at=_SESSION_UPDATED_AT,
        store=store,
    )

    assert result.turn is session.conversation.turns[-1]
    assert session.sync_state is SessionSyncState.CLEAN
    assert store.save_calls == 1

    persisted = store.states[
        session.session_id
    ]

    assert (
        persisted["conversation"]["turns"][-1]
        ["user"]["content"]
        == "mensagem persistente"
    )
    assert (
        persisted["conversation"]["turns"][-1]
        ["assistant"]["content"]
        == "persistida"
    )


def test_execute_session_message_builds_request_from_logical_history(
    monkeypatch,
) -> None:
    store = SessionExecutionStateStore()
    session = _execution_session()

    previous_turn = Turn(
        user=Message(
            role=MessageRole.USER,
            content="pergunta anterior",
        ),
        assistant=Message(
            role=MessageRole.ASSISTANT,
            content="resposta anterior",
        ),
    )

    session.conversation.append(
        previous_turn
    )

    captured: list[ConversationRequest] = []

    def fake_execute(
        request: ConversationRequest,
        **kwargs,
    ) -> ConversationExecutionResult:
        del kwargs
        captured.append(request)

        return ConversationExecutionResult(
            prompt_result=PromptResult(
                response="nova resposta",
                profile="general",
                model="model-test",
                state="routed",
                route_id="route-test",
                output_tokens=10,
                generation_duration_ns=1_000_000,
                tokens_per_second=10.0,
            ),
            effective_context=request.effective_context,
        )

    monkeypatch.setattr(
        "villaz_cli.conversation_execution.execute_conversation_request",
        fake_execute,
    )

    result = execute_session_message(
        session,
        Message(
            role=MessageRole.USER,
            content="nova pergunta",
        ),
        updated_at=_SESSION_UPDATED_AT,
        store=store,
    )

    assert captured[0].effective_context.turns == (
        previous_turn,
    )

    assert session.conversation.turns == (
        previous_turn,
        result.turn,
    )
