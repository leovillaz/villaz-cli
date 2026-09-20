from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from villaz_cli.conversation import (
    ConversationResult,
    ConversationResultKind,
    EffectiveInferenceContext,
    LogicalConversationHistory,
    Message,
    MessageRole,
    Turn,
)


class SessionLifecycle(StrEnum):
    ACTIVE = "active"
    CLOSED = "closed"
    DELETED = "deleted"


class PersistenceMode(StrEnum):
    EPHEMERAL = "ephemeral"
    PERSISTENT = "persistent"


class SessionAuthority(StrEnum):
    LOCAL = "local"
    REMOTE = "remote"


class ProfileModeKind(StrEnum):
    AUTO = "auto"
    EXPLICIT = "explicit"


@dataclass(frozen=True, slots=True)
class ProfileMode:
    kind: ProfileModeKind
    profile_id: str | None = None

    def __post_init__(self) -> None:
        if self.kind is ProfileModeKind.AUTO:
            if self.profile_id is not None:
                raise ValueError(
                    "ProfileMode AUTO não pode possuir profile_id."
                )
            return

        if self.profile_id is None or not self.profile_id.strip():
            raise ValueError(
                "ProfileMode EXPLICIT exige um profile_id não vazio."
            )

    @classmethod
    def auto(cls) -> "ProfileMode":
        return cls(kind=ProfileModeKind.AUTO)

    @classmethod
    def explicit(cls, profile_id: str) -> "ProfileMode":
        return cls(
            kind=ProfileModeKind.EXPLICIT,
            profile_id=profile_id,
        )


class SessionSyncState(StrEnum):
    CLEAN = "clean"
    DIRTY = "dirty"


class SessionLifecycleError(Exception):
    """Raised when an operation is incompatible with the Session lifecycle."""


@dataclass(slots=True)
class Session:
    session_id: str
    conversation: LogicalConversationHistory
    persistence_mode: PersistenceMode
    authority: SessionAuthority
    profile_mode: ProfileMode
    created_at: datetime
    updated_at: datetime
    lifecycle: SessionLifecycle = SessionLifecycle.ACTIVE
    sync_state: SessionSyncState = SessionSyncState.CLEAN

    def __post_init__(self) -> None:
        if (
            self.persistence_mode is PersistenceMode.EPHEMERAL
            and self.sync_state is SessionSyncState.DIRTY
        ):
            raise ValueError(
                "Uma Session EPHEMERAL não pode possuir estado DIRTY."
            )

    def _record_change(self, *, updated_at: datetime) -> None:
        self.updated_at = updated_at

        if self.persistence_mode is PersistenceMode.PERSISTENT:
            self.sync_state = SessionSyncState.DIRTY

    def commit_turn(
        self,
        turn: Turn,
        *,
        updated_at: datetime,
    ) -> None:
        if self.lifecycle is not SessionLifecycle.ACTIVE:
            raise SessionLifecycleError(
                "Somente uma Session ACTIVE pode confirmar um Turn."
            )

        self.conversation.append(turn)
        self._record_change(
            updated_at=updated_at,
        )

    def change_profile_mode(
        self,
        profile_mode: ProfileMode,
        *,
        updated_at: datetime,
    ) -> None:
        if self.lifecycle is not SessionLifecycle.ACTIVE:
            raise SessionLifecycleError(
                "Somente uma Session ACTIVE pode alterar o profile mode."
            )

        self.profile_mode = profile_mode
        self._record_change(
            updated_at=updated_at,
        )

    def close(self, *, updated_at: datetime) -> None:
        if self.lifecycle is not SessionLifecycle.ACTIVE:
            raise SessionLifecycleError(
                "Somente uma Session ACTIVE pode ser fechada."
            )

        self.lifecycle = SessionLifecycle.CLOSED
        self._record_change(updated_at=updated_at)

    def resume(self, *, updated_at: datetime) -> None:
        if self.lifecycle is not SessionLifecycle.CLOSED:
            raise SessionLifecycleError(
                "Somente uma Session CLOSED pode ser retomada."
            )

        self.lifecycle = SessionLifecycle.ACTIVE
        self._record_change(updated_at=updated_at)

    def delete(self, *, updated_at: datetime) -> None:
        if self.lifecycle is SessionLifecycle.DELETED:
            raise SessionLifecycleError(
                "Uma Session DELETED não pode ser excluída novamente."
            )

        self.lifecycle = SessionLifecycle.DELETED
        self._record_change(updated_at=updated_at)

    def reset_conversation(self, *, updated_at: datetime) -> None:
        if self.lifecycle is not SessionLifecycle.ACTIVE:
            raise SessionLifecycleError(
                "Somente uma Session ACTIVE pode resetar a Conversation."
            )

        self.conversation.reset()
        self._record_change(updated_at=updated_at)

    def mark_clean(self) -> None:
        if self.persistence_mode is not PersistenceMode.PERSISTENT:
            return

        self.sync_state = SessionSyncState.CLEAN


@dataclass(frozen=True, slots=True)
class ConversationRequest:
    current_message: Message
    effective_context: EffectiveInferenceContext
    profile_mode: ProfileMode

    def __post_init__(self) -> None:
        if self.current_message.role is not MessageRole.USER:
            raise ValueError(
                "current_message deve possuir role 'user'."
            )

    @classmethod
    def from_session(
        cls,
        session: Session,
        *,
        current_message: Message,
    ) -> "ConversationRequest":
        return cls(
            current_message=current_message,
            effective_context=(
                EffectiveInferenceContext.from_history(
                    session.conversation
                )
            ),
            profile_mode=session.profile_mode,
        )
    def materialize_turn(
        self,
        result: ConversationResult,
    ) -> Turn | None:
        if result.kind is ConversationResultKind.FAILURE:
            return None

        assert result.assistant_message is not None

        return Turn(
            user=self.current_message,
            assistant=result.assistant_message,
        )


def commit_conversation_result(
    session: Session,
    request: ConversationRequest,
    result: ConversationResult,
    *,
    updated_at: datetime,
) -> Turn | None:
    turn = request.materialize_turn(
        result
    )

    if turn is None:
        return None

    session.commit_turn(
        turn,
        updated_at=updated_at,
    )

    return turn
