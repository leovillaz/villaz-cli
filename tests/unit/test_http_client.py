import json
import httpx
import pytest

from villaz_cli.http_client import (
    PromptResult,
    RouterAPIError,
    RouterProtocolError,
    HealthResult,
    send_prompt,
    get_health,
)


def test_send_prompt_posts_expected_contract_and_parses_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1/prompt"
        assert json.loads(request.content) == {
                "message": "Revise este código"
            }

        return httpx.Response(
            200,
            json={
                "response": "Resposta segura.",
                "profile": "code-review-security",
                "model": "qwen2.5-coder:14b",
                "state": "routed",
                "route_id": "ROUTE-REVIEW-001",
            },
        )

    result = send_prompt(
        "Revise este código",
        transport=httpx.MockTransport(handler),
    )

    assert result == PromptResult(
        response="Resposta segura.",
        profile="code-review-security",
        model="qwen2.5-coder:14b",
        state="routed",
        route_id="ROUTE-REVIEW-001",
    )


def test_send_prompt_translates_router_error_contract() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "error": {
                    "code": "UNROUTED",
                    "message": "The request could not be routed.",
                }
            },
        )

    with pytest.raises(RouterAPIError) as exc_info:
        send_prompt(
            "Olá",
            transport=httpx.MockTransport(handler),
        )

    assert exc_info.value.code == "UNROUTED"
    assert exc_info.value.message == "The request could not be routed."


def test_send_prompt_rejects_invalid_success_contract() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "response": "Resposta",
                "profile": "code-review-security",
            },
        )

    with pytest.raises(RouterProtocolError):
        send_prompt(
            "Revise código",
            transport=httpx.MockTransport(handler),
        )

def test_send_prompt_includes_explicit_profile_when_selected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content) == {
            "message": "Teste",
            "explicit_profile": "code-review-security",
        }

        return httpx.Response(
            200,
            json={
                "response": "OK",
                "profile": "code-review-security",
                "model": "qwen2.5-coder:14b",
                "state": "explicit",
                "route_id": None,
            },
        )

    result = send_prompt(
        "Teste",
        explicit_profile="code-review-security",
        transport=httpx.MockTransport(handler),
    )

    assert result.state == "explicit"
    assert result.profile == "code-review-security"
    assert result.route_id is None

def test_get_health_requests_live_and_ready_and_parses_success() -> None:
    requested_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_paths.append(request.url.path)

        if request.url.path == "/health/live":
            return httpx.Response(
                200,
                json={"status": "alive"},
            )

        if request.url.path == "/health/ready":
            return httpx.Response(
                200,
                json={"status": "ready"},
            )

        raise AssertionError(
            f"endpoint inesperado: {request.url.path}"
        )

    result = get_health(
        transport=httpx.MockTransport(handler),
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
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health/live":
            return httpx.Response(
                200,
                json={"status": "unexpected"},
            )

        return httpx.Response(
            200,
            json={"status": "ready"},
        )

    with pytest.raises(RouterProtocolError):
        get_health(
            transport=httpx.MockTransport(handler),
        )


def test_get_health_rejects_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health/live":
            return httpx.Response(
                503,
                json={"status": "unavailable"},
            )

        return httpx.Response(
            200,
            json={"status": "ready"},
        )

    with pytest.raises(RouterProtocolError):
        get_health(
            transport=httpx.MockTransport(handler),
        )
