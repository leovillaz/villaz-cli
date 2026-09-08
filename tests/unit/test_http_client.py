import json
import httpx
import pytest

from villaz_cli.http_client import (
    PromptResult,
    RouterAPIError,
    RouterProtocolError,
    send_prompt,
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
