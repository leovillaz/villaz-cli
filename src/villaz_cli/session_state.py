from datetime import datetime
from typing import Any

from villaz_cli.conversation import (
    LogicalConversationHistory,
    Message,
    MessageRole,
    Turn,
)
from villaz_cli.session import (
    PersistenceMode,
    ProfileMode,
    ProfileModeKind,
    Session,
    SessionAuthority,
    SessionLifecycle,
    SessionSyncState,
)


SESSION_SCHEMA_VERSION = 1


class SessionStateError(Exception):
    """Base error raised for invalid persisted Session state."""


class UnsupportedSessionSchemaError(SessionStateError):
    """Raised when the persisted schema version is not supported."""


def _require_dict(
    payload: Any,
    field: str,
) -> dict[str, Any]:
    value = payload.get(field)

    if not isinstance(value, dict):
        raise SessionStateError(
            f"Estado persistido inválido: campo '{field}' ausente ou inválido."
        )

    return value


def _require_list(
    payload: dict[str, Any],
    field: str,
) -> list[Any]:
    value = payload.get(field)

    if not isinstance(value, list):
        raise SessionStateError(
            f"Estado persistido inválido: campo '{field}' ausente ou inválido."
        )

    return value


def _require_string(
    payload: dict[str, Any],
    field: str,
) -> str:
    value = payload.get(field)

    if not isinstance(value, str):
        raise SessionStateError(
            f"Estado persistido inválido: campo '{field}' ausente ou inválido."
        )

    return value


def _parse_datetime(
    payload: dict[str, Any],
    field: str,
) -> datetime:
    raw_value = _require_string(payload, field)

    try:
        return datetime.fromisoformat(raw_value)
    except ValueError as exc:
        raise SessionStateError(
            f"Estado persistido inválido: campo '{field}' não contém datetime válido."
        ) from exc


def _serialize_profile_mode(
    profile_mode: ProfileMode,
) -> dict[str, Any]:
    return {
        "kind": profile_mode.kind.value,
        "profile_id": profile_mode.profile_id,
    }


def _parse_profile_mode(
    payload: dict[str, Any],
) -> ProfileMode:
    raw_kind = _require_string(payload, "kind")

    try:
        kind = ProfileModeKind(raw_kind)
    except ValueError as exc:
        raise SessionStateError(
            "Estado persistido inválido: profile mode desconhecido."
        ) from exc

    profile_id = payload.get("profile_id")

    if profile_id is not None and not isinstance(profile_id, str):
        raise SessionStateError(
            "Estado persistido inválido: campo 'profile_id' inválido."
        )

    try:
        return ProfileMode(
            kind=kind,
            profile_id=profile_id,
        )
    except ValueError as exc:
        raise SessionStateError(
            "Estado persistido inválido: combinação de profile mode inválida."
        ) from exc


def _serialize_turn(
    turn: Turn,
) -> dict[str, Any]:
    return {
        "user": {
            "role": turn.user.role.value,
            "content": turn.user.content,
        },
        "assistant": {
            "role": turn.assistant.role.value,
            "content": turn.assistant.content,
        },
    }


def _parse_message(
    payload: dict[str, Any],
    *,
    expected_role: MessageRole,
) -> Message:
    raw_role = _require_string(payload, "role")
    content = _require_string(payload, "content")

    try:
        role = MessageRole(raw_role)
    except ValueError as exc:
        raise SessionStateError(
            "Estado persistido inválido: role de mensagem desconhecida."
        ) from exc

    if role is not expected_role:
        raise SessionStateError(
            "Estado persistido inválido: role de mensagem incompatível."
        )

    return Message(
        role=role,
        content=content,
    )


def _parse_turn(
    payload: Any,
) -> Turn:
    if not isinstance(payload, dict):
        raise SessionStateError(
            "Estado persistido inválido: turn deve ser um objeto."
        )

    user_payload = _require_dict(payload, "user")
    assistant_payload = _require_dict(payload, "assistant")

    return Turn(
        user=_parse_message(
            user_payload,
            expected_role=MessageRole.USER,
        ),
        assistant=_parse_message(
            assistant_payload,
            expected_role=MessageRole.ASSISTANT,
        ),
    )


def session_to_state(
    session: Session,
) -> dict[str, Any]:
    if session.persistence_mode is not PersistenceMode.PERSISTENT:
        raise SessionStateError(
            "Somente uma Session PERSISTENT pode gerar estado persistível."
        )

    return {
        "schema_version": SESSION_SCHEMA_VERSION,
        "session_id": session.session_id,
        "lifecycle": session.lifecycle.value,
        "persistence_mode": session.persistence_mode.value,
        "authority": session.authority.value,
        "profile_mode": _serialize_profile_mode(session.profile_mode),
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
        "conversation": {
            "turns": [
                _serialize_turn(turn)
                for turn in session.conversation.turns
            ],
        },
    }


def session_from_state(
    payload: Any,
) -> Session:
    if not isinstance(payload, dict):
        raise SessionStateError(
            "Estado persistido inválido: raiz deve ser um objeto."
        )

    schema_version = payload.get("schema_version")

    if type(schema_version) is not int:
        raise SessionStateError(
            "Estado persistido inválido: schema_version ausente ou inválido."
        )

    if schema_version != SESSION_SCHEMA_VERSION:
        raise UnsupportedSessionSchemaError(
            f"schema_version não suportado: {schema_version}."
        )

    session_id = _require_string(payload, "session_id")
    raw_lifecycle = _require_string(payload, "lifecycle")
    raw_persistence_mode = _require_string(
        payload,
        "persistence_mode",
    )
    raw_authority = _require_string(payload, "authority")

    try:
        lifecycle = SessionLifecycle(raw_lifecycle)
    except ValueError as exc:
        raise SessionStateError(
            "Estado persistido inválido: lifecycle desconhecido."
        ) from exc

    try:
        persistence_mode = PersistenceMode(raw_persistence_mode)
    except ValueError as exc:
        raise SessionStateError(
            "Estado persistido inválido: persistence mode desconhecido."
        ) from exc

    if persistence_mode is not PersistenceMode.PERSISTENT:
        raise SessionStateError(
            "Estado persistido inválido: Session restaurável deve ser PERSISTENT."
        )

    try:
        authority = SessionAuthority(raw_authority)
    except ValueError as exc:
        raise SessionStateError(
            "Estado persistido inválido: authority desconhecida."
        ) from exc

    profile_mode = _parse_profile_mode(
        _require_dict(payload, "profile_mode")
    )

    created_at = _parse_datetime(payload, "created_at")
    updated_at = _parse_datetime(payload, "updated_at")

    conversation_payload = _require_dict(
        payload,
        "conversation",
    )
    raw_turns = _require_list(
        conversation_payload,
        "turns",
    )

    conversation = LogicalConversationHistory()

    for raw_turn in raw_turns:
        conversation.append(
            _parse_turn(raw_turn)
        )

    return Session(
        session_id=session_id,
        conversation=conversation,
        persistence_mode=PersistenceMode.PERSISTENT,
        authority=authority,
        profile_mode=profile_mode,
        created_at=created_at,
        updated_at=updated_at,
        lifecycle=lifecycle,
        sync_state=SessionSyncState.CLEAN,
    )
