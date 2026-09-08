from dataclasses import dataclass
from typing import Any

import httpx


DEFAULT_ROUTER_URL = "http://127.0.0.1:8000"
DEFAULT_TIMEOUT_SECONDS = 120.0


class RouterClientError(Exception):
    """Base error raised by the Villaz Router HTTP client."""


class RouterConnectionError(RouterClientError):
    """Raised when the Router cannot be reached."""


class RouterProtocolError(RouterClientError):
    """Raised when the Router response violates the expected public contract."""


class RouterAPIError(RouterClientError):
    """Raised when the Router returns a public API error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class PromptResult:
    response: str
    profile: str
    model: str
    state: str
    route_id: str | None


def _require_string(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str):
        raise RouterProtocolError(
            f"Resposta inválida do Router: campo '{field}' ausente ou inválido."
        )
    return value


def _parse_success(payload: Any) -> PromptResult:
    if not isinstance(payload, dict):
        raise RouterProtocolError("Resposta inválida do Router: JSON inesperado.")

    response = _require_string(payload, "response")
    profile = _require_string(payload, "profile")
    model = _require_string(payload, "model")
    state = _require_string(payload, "state")

    route_id = payload.get("route_id")
    if route_id is not None and not isinstance(route_id, str):
        raise RouterProtocolError(
            "Resposta inválida do Router: campo 'route_id' inválido."
        )

    return PromptResult(
        response=response,
        profile=profile,
        model=model,
        state=state,
        route_id=route_id,
    )


def _parse_error(payload: Any) -> RouterAPIError | None:
    if not isinstance(payload, dict):
        return None

    error = payload.get("error")
    if not isinstance(error, dict):
        return None

    code = error.get("code")
    message = error.get("message")

    if not isinstance(code, str) or not isinstance(message, str):
        raise RouterProtocolError(
            "Resposta de erro inválida recebida do Router."
        )

    return RouterAPIError(code=code, message=message)


def send_prompt(
    message: str,
    *,
    base_url: str = DEFAULT_ROUTER_URL,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    transport: httpx.BaseTransport | None = None,
) -> PromptResult:
    try:
        with httpx.Client(
            base_url=base_url,
            timeout=timeout,
            transport=transport,
        ) as client:
            response = client.post(
                "/v1/prompt",
                json={"message": message},
            )
    except httpx.RequestError as exc:
        raise RouterConnectionError(
            f"Não foi possível conectar ao Router em {base_url}."
        ) from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise RouterProtocolError(
            "O Router retornou uma resposta que não é JSON válido."
        ) from exc

    api_error = _parse_error(payload)
    if api_error is not None:
        raise api_error

    if response.is_error:
        raise RouterProtocolError(
            f"O Router respondeu com HTTP {response.status_code}."
        )

    return _parse_success(payload)
