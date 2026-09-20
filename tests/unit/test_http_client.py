import json

import httpx
import pytest

from villaz_cli.conversation import (
    EffectiveInferenceContext,
    Message,
    MessageRole,
    Turn,
)
from villaz_cli.http_client import (
    HealthResult,
    PromptResult,
    RouterAPIError,
    RouterProtocolError,
    get_health,
    send_conversation_request,
    send_prompt,
)
from villaz_cli.session import (
    ConversationRequest,
    ProfileMode,
)


def _success_response(
    *,
    state: str = "routed",
    profile: str = "code-review-security",
    route_id: str | None = (
        "ROUTE-REVIEW-001"
    ),
) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "response": "Resposta segura.",
            "profile": profile,
            "model": "qwen2.5-coder:14b",
            "state": state,
            "route_id": route_id,
            "metrics": {
                "output_tokens": 42,
                "generation_duration_ns": (
                    1_500_000_000
                ),
                "tokens_per_second": 28.0,
            },
        },
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


def _conversation_request(
    *,
    turns: tuple[Turn, ...] = (),
    omitted_turn_count: int = 0,
    profile_mode: ProfileMode | None = None,
    current_message: str = "pergunta atual",
) -> ConversationRequest:
    return ConversationRequest(
        current_message=Message(
            role=MessageRole.USER,
            content=current_message,
        ),
        effective_context=(
            EffectiveInferenceContext(
                turns=turns,
                omitted_turn_count=(
                    omitted_turn_count
                ),
            )
        ),
        profile_mode=(
            profile_mode
            if profile_mode is not None
            else ProfileMode.auto()
        ),
    )


def test_send_prompt_posts_expected_contract_and_parses_success() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert request.method == "POST"
        assert (
            request.url.path
            == "/v1/prompt"
        )
        assert json.loads(
            request.content
        ) == {
            "message": "Revise este código",
        }

        return _success_response()

    result = send_prompt(
        "Revise este código",
        transport=httpx.MockTransport(
            handler
        ),
    )

    assert result == PromptResult(
        response="Resposta segura.",
        profile="code-review-security",
        model="qwen2.5-coder:14b",
        state="routed",
        route_id="ROUTE-REVIEW-001",
        output_tokens=42,
        generation_duration_ns=(
            1_500_000_000
        ),
        tokens_per_second=28.0,
    )


def test_send_prompt_translates_router_error_contract() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "error": {
                    "code": "UNROUTED",
                    "message": (
                        "The request could not "
                        "be routed."
                    ),
                }
            },
        )

    with pytest.raises(
        RouterAPIError
    ) as exc_info:
        send_prompt(
            "Olá",
            transport=httpx.MockTransport(
                handler
            ),
        )

    assert (
        exc_info.value.code
        == "UNROUTED"
    )
    assert (
        exc_info.value.message
        == "The request could not be routed."
    )


def test_send_prompt_rejects_invalid_success_contract() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "response": "Resposta",
                "profile": (
                    "code-review-security"
                ),
            },
        )

    with pytest.raises(
        RouterProtocolError
    ):
        send_prompt(
            "Revise código",
            transport=httpx.MockTransport(
                handler
            ),
        )


def test_send_prompt_rejects_missing_metrics() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "response": "Resposta",
                "profile": (
                    "code-review-security"
                ),
                "model": (
                    "qwen2.5-coder:14b"
                ),
                "state": "routed",
                "route_id": (
                    "ROUTE-REVIEW-001"
                ),
            },
        )

    with pytest.raises(
        RouterProtocolError
    ):
        send_prompt(
            "Revise código",
            transport=httpx.MockTransport(
                handler
            ),
        )


@pytest.mark.parametrize(
    (
        "field_name",
        "invalid_value",
    ),
    [
        (
            "output_tokens",
            True,
        ),
        (
            "output_tokens",
            42.0,
        ),
        (
            "generation_duration_ns",
            "1500000000",
        ),
        (
            "tokens_per_second",
            28,
        ),
    ],
)
def test_send_prompt_rejects_invalid_metric_types(
    field_name: str,
    invalid_value: object,
) -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        metrics: dict[str, object] = {
            "output_tokens": 42,
            "generation_duration_ns": (
                1_500_000_000
            ),
            "tokens_per_second": 28.0,
        }
        metrics[field_name] = (
            invalid_value
        )

        return httpx.Response(
            200,
            json={
                "response": "Resposta",
                "profile": (
                    "code-review-security"
                ),
                "model": (
                    "qwen2.5-coder:14b"
                ),
                "state": "routed",
                "route_id": (
                    "ROUTE-REVIEW-001"
                ),
                "metrics": metrics,
            },
        )

    with pytest.raises(
        RouterProtocolError
    ):
        send_prompt(
            "Revise código",
            transport=httpx.MockTransport(
                handler
            ),
        )


def test_send_prompt_includes_explicit_profile_when_selected() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert json.loads(
            request.content
        ) == {
            "message": "Teste",
            "explicit_profile": (
                "code-review-security"
            ),
        }

        return _success_response(
            state="explicit",
            route_id=None,
        )

    result = send_prompt(
        "Teste",
        explicit_profile=(
            "code-review-security"
        ),
        transport=httpx.MockTransport(
            handler
        ),
    )

    assert result.state == "explicit"
    assert (
        result.profile
        == "code-review-security"
    )
    assert result.route_id is None


def test_send_conversation_request_sends_empty_history_explicitly() -> None:
    conversation_request = (
        _conversation_request()
    )

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert json.loads(
            request.content
        ) == {
            "message": "pergunta atual",
            "history": [],
        }

        return _success_response()

    send_conversation_request(
        conversation_request,
        transport=httpx.MockTransport(
            handler
        ),
    )


def test_send_conversation_request_preserves_turn_order_and_content() -> None:
    first = _turn(
        "  primeira\nlinha  ",
        " resposta 1\n",
    )
    second = _turn(
        "segunda\tpergunta",
        "segunda resposta  ",
    )

    conversation_request = (
        _conversation_request(
            turns=(
                first,
                second,
            ),
            current_message=(
                "  mensagem atual\n"
            ),
        )
    )

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert json.loads(
            request.content
        ) == {
            "message": (
                "  mensagem atual\n"
            ),
            "history": [
                {
                    "user": (
                        "  primeira\nlinha  "
                    ),
                    "assistant": (
                        " resposta 1\n"
                    ),
                },
                {
                    "user": (
                        "segunda\tpergunta"
                    ),
                    "assistant": (
                        "segunda resposta  "
                    ),
                },
            ],
        }

        return _success_response()

    send_conversation_request(
        conversation_request,
        transport=httpx.MockTransport(
            handler
        ),
    )


def test_send_conversation_request_does_not_send_omitted_turn_count() -> None:
    conversation_request = (
        _conversation_request(
            turns=(
                _turn(
                    "restante",
                    "resposta restante",
                ),
            ),
            omitted_turn_count=3,
        )
    )

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        payload = json.loads(
            request.content
        )

        assert payload == {
            "message": "pergunta atual",
            "history": [
                {
                    "user": "restante",
                    "assistant": (
                        "resposta restante"
                    ),
                }
            ],
        }
        assert (
            "omitted_turn_count"
            not in payload
        )

        return _success_response()

    send_conversation_request(
        conversation_request,
        transport=httpx.MockTransport(
            handler
        ),
    )


def test_send_conversation_request_sends_only_effective_context() -> None:
    first = _turn(
        "primeira",
        "resposta 1",
    )
    second = _turn(
        "segunda",
        "resposta 2",
    )

    full_context = (
        EffectiveInferenceContext(
            turns=(
                first,
                second,
            ),
        )
    )
    reduced_context = (
        full_context.without_oldest_turn()
    )

    conversation_request = (
        ConversationRequest(
            current_message=Message(
                role=MessageRole.USER,
                content="terceira",
            ),
            effective_context=(
                reduced_context
            ),
            profile_mode=(
                ProfileMode.auto()
            ),
        )
    )

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert json.loads(
            request.content
        ) == {
            "message": "terceira",
            "history": [
                {
                    "user": "segunda",
                    "assistant": (
                        "resposta 2"
                    ),
                }
            ],
        }

        return _success_response()

    send_conversation_request(
        conversation_request,
        transport=httpx.MockTransport(
            handler
        ),
    )


def test_send_conversation_request_auto_profile_omits_explicit_profile() -> None:
    conversation_request = (
        _conversation_request(
            profile_mode=(
                ProfileMode.auto()
            ),
        )
    )

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        payload = json.loads(
            request.content
        )

        assert (
            "explicit_profile"
            not in payload
        )

        return _success_response()

    send_conversation_request(
        conversation_request,
        transport=httpx.MockTransport(
            handler
        ),
    )


def test_send_conversation_request_explicit_profile_is_preserved_exactly() -> None:
    conversation_request = (
        _conversation_request(
            profile_mode=(
                ProfileMode.explicit(
                    "  code-review-security  "
                )
            ),
        )
    )

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert json.loads(
            request.content
        ) == {
            "message": "pergunta atual",
            "history": [],
            "explicit_profile": (
                "  code-review-security  "
            ),
        }

        return _success_response(
            state="explicit",
            profile=(
                "  code-review-security  "
            ),
            route_id=None,
        )

    send_conversation_request(
        conversation_request,
        transport=httpx.MockTransport(
            handler
        ),
    )


def test_send_conversation_request_does_not_mutate_request() -> None:
    turn = _turn(
        "anterior",
        "resposta",
    )

    conversation_request = (
        _conversation_request(
            turns=(turn,),
            omitted_turn_count=2,
            profile_mode=(
                ProfileMode.explicit(
                    "code-review-security"
                )
            ),
        )
    )

    original_current_message = (
        conversation_request.current_message
    )
    original_context = (
        conversation_request
        .effective_context
    )
    original_profile_mode = (
        conversation_request.profile_mode
    )

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return _success_response(
            state="explicit",
            route_id=None,
        )

    send_conversation_request(
        conversation_request,
        transport=httpx.MockTransport(
            handler
        ),
    )

    assert (
        conversation_request
        .current_message
        is original_current_message
    )
    assert (
        conversation_request
        .effective_context
        is original_context
    )
    assert (
        conversation_request.profile_mode
        is original_profile_mode
    )
    assert (
        conversation_request
        .effective_context.turns
        == (turn,)
    )
    assert (
        conversation_request
        .effective_context
        .omitted_turn_count
        == 2
    )


def test_send_conversation_request_propagates_context_overflow_without_retry() -> None:
    request_count = 0

    conversation_request = (
        _conversation_request(
            turns=(
                _turn(
                    "anterior",
                    "resposta",
                ),
            ),
        )
    )

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        nonlocal request_count

        request_count += 1

        return httpx.Response(
            422,
            json={
                "error": {
                    "code": (
                        "CONTEXT_OVERFLOW"
                    ),
                    "message": (
                        "The request exceeds "
                        "the available model "
                        "context."
                    ),
                }
            },
        )

    with pytest.raises(
        RouterAPIError
    ) as exc_info:
        send_conversation_request(
            conversation_request,
            transport=(
                httpx.MockTransport(
                    handler
                )
            ),
        )

    assert (
        exc_info.value.code
        == "CONTEXT_OVERFLOW"
    )
    assert (
        exc_info.value.message
        == (
            "The request exceeds the "
            "available model context."
        )
    )
    assert request_count == 1


def test_send_conversation_request_preserves_generic_router_error_without_retry() -> None:
    request_count = 0

    conversation_request = (
        _conversation_request()
    )

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        nonlocal request_count

        request_count += 1

        return httpx.Response(
            422,
            json={
                "error": {
                    "code": "UNROUTED",
                    "message": (
                        "The request could "
                        "not be routed."
                    ),
                }
            },
        )

    with pytest.raises(
        RouterAPIError
    ) as exc_info:
        send_conversation_request(
            conversation_request,
            transport=(
                httpx.MockTransport(
                    handler
                )
            ),
        )

    assert (
        exc_info.value.code
        == "UNROUTED"
    )
    assert request_count == 1


def test_get_health_requests_live_and_ready_and_parses_success() -> None:
    requested_paths: list[str] = []

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        requested_paths.append(
            request.url.path
        )

        if (
            request.url.path
            == "/health/live"
        ):
            return httpx.Response(
                200,
                json={
                    "status": "alive",
                },
            )

        if (
            request.url.path
            == "/health/ready"
        ):
            return httpx.Response(
                200,
                json={
                    "status": "ready",
                },
            )

        raise AssertionError(
            f"endpoint inesperado: "
            f"{request.url.path}"
        )

    result = get_health(
        transport=httpx.MockTransport(
            handler
        ),
    )

    assert requested_paths == [
        "/health/live",
        "/health/ready",
    ]
    assert result == HealthResult(
        live="alive",
        ready="ready",
    )


def test_get_health_rejects_unexpected_live_status() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        if (
            request.url.path
            == "/health/live"
        ):
            return httpx.Response(
                200,
                json={
                    "status": (
                        "unexpected"
                    ),
                },
            )

        return httpx.Response(
            200,
            json={
                "status": "ready",
            },
        )

    with pytest.raises(
        RouterProtocolError
    ):
        get_health(
            transport=httpx.MockTransport(
                handler
            ),
        )


def test_get_health_rejects_http_error() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        if (
            request.url.path
            == "/health/live"
        ):
            return httpx.Response(
                503,
                json={
                    "status": (
                        "unavailable"
                    ),
                },
            )

        return httpx.Response(
            200,
            json={
                "status": "ready",
            },
        )

    with pytest.raises(
        RouterProtocolError
    ):
        get_health(
            transport=httpx.MockTransport(
                handler
            ),
        )
