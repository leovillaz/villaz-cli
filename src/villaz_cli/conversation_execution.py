from dataclasses import dataclass
from datetime import datetime

import httpx

from villaz_cli.conversation import (
    ConversationResult,
    EffectiveInferenceContext,
    Message,
    MessageRole,
    Turn,
)
from villaz_cli.http_client import (
    DEFAULT_ROUTER_URL,
    DEFAULT_TIMEOUT_SECONDS,
    PromptResult,
    RouterAPIError,
    send_conversation_request,
)
from villaz_cli.session import (
    ConversationRequest,
    Session,
)
from villaz_cli.session_persistence import (
    SessionStateStore,
    commit_conversation_result_with_autosave,
)


_CONTEXT_OVERFLOW_CODE = "CONTEXT_OVERFLOW"


@dataclass(frozen=True, slots=True)
class ConversationExecutionResult:
    prompt_result: PromptResult
    effective_context: EffectiveInferenceContext


@dataclass(frozen=True, slots=True)
class SessionMessageExecutionResult:
    prompt_result: PromptResult
    effective_context: EffectiveInferenceContext
    turn: Turn


def execute_conversation_request(
    request: ConversationRequest,
    *,
    base_url: str = DEFAULT_ROUTER_URL,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    transport: httpx.BaseTransport | None = None,
) -> ConversationExecutionResult:
    current_request = request

    while True:
        try:
            prompt_result = send_conversation_request(
                current_request,
                base_url=base_url,
                timeout=timeout,
                transport=transport,
            )

            return ConversationExecutionResult(
                prompt_result=prompt_result,
                effective_context=(
                    current_request.effective_context
                ),
            )

        except RouterAPIError as exc:
            if exc.code != _CONTEXT_OVERFLOW_CODE:
                raise

            if not current_request.effective_context.turns:
                raise

            current_request = ConversationRequest(
                current_message=(
                    current_request.current_message
                ),
                effective_context=(
                    current_request
                    .effective_context
                    .without_oldest_turn()
                ),
                profile_mode=(
                    current_request.profile_mode
                ),
            )


def to_conversation_result(
    execution_result: ConversationExecutionResult,
) -> ConversationResult:
    return ConversationResult.success(
        Message(
            role=MessageRole.ASSISTANT,
            content=(
                execution_result
                .prompt_result
                .response
            ),
        )
    )


def execute_session_message(
    session: Session,
    current_message: Message,
    *,
    updated_at: datetime,
    store: SessionStateStore,
    base_url: str = DEFAULT_ROUTER_URL,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    transport: httpx.BaseTransport | None = None,
) -> SessionMessageExecutionResult:
    request = ConversationRequest.from_session(
        session,
        current_message=current_message,
    )

    execution_result = execute_conversation_request(
        request,
        base_url=base_url,
        timeout=timeout,
        transport=transport,
    )

    conversation_result = to_conversation_result(
        execution_result
    )

    turn = commit_conversation_result_with_autosave(
        session,
        request,
        conversation_result,
        updated_at=updated_at,
        store=store,
    )

    assert turn is not None

    return SessionMessageExecutionResult(
        prompt_result=execution_result.prompt_result,
        effective_context=execution_result.effective_context,
        turn=turn,
    )
