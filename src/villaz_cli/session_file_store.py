import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from villaz_cli.session_persistence import (
    SessionNotFoundError,
    SessionStorageError,
)


class SessionCorruptStateError(SessionStorageError):
    """Raised when persisted Session data is physically corrupt or inconsistent."""


class JsonSessionStateStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    @staticmethod
    def _storage_key(session_id: str) -> str:
        return hashlib.sha256(
            session_id.encode("utf-8")
        ).hexdigest()

    def _target_path(
        self,
        session_id: str,
    ) -> Path:
        return self.root / (
            f"{self._storage_key(session_id)}.json"
        )

    def _ensure_root(self) -> None:
        try:
            if self.root.exists():
                if not self.root.is_dir():
                    raise SessionStorageError(
                        "O diretório de Sessions está ocupado por um arquivo."
                    )
                return

            self.root.mkdir(
                parents=True,
                mode=0o700,
                exist_ok=True,
            )

            if os.name != "nt":
                os.chmod(
                    self.root,
                    0o700,
                )
        except OSError as exc:
            raise SessionStorageError(
                "Não foi possível preparar o diretório de Sessions."
            ) from exc

    def _existing_root(self) -> bool:
        try:
            if not self.root.exists():
                return False

            if not self.root.is_dir():
                raise SessionStorageError(
                    "O diretório de Sessions está ocupado por um arquivo."
                )

            return True
        except OSError as exc:
            raise SessionStorageError(
                "Não foi possível acessar o diretório de Sessions."
            ) from exc

    @staticmethod
    def _reject_symlink(
        path: Path,
    ) -> None:
        try:
            if path.is_symlink():
                raise SessionStorageError(
                    "O arquivo persistido de Session não pode ser um symlink."
                )
        except OSError as exc:
            raise SessionStorageError(
                "Não foi possível validar o arquivo persistido de Session."
            ) from exc

    @staticmethod
    def _encode_state(
        state: dict[str, Any],
    ) -> bytes:
        try:
            serialized = json.dumps(
                state,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        except (TypeError, ValueError) as exc:
            raise SessionStorageError(
                "O estado da Session não pode ser serializado como JSON."
            ) from exc

        return (
            serialized + "\n"
        ).encode("utf-8")

    def save(
        self,
        *,
        session_id: str,
        state: dict[str, Any],
    ) -> None:
        self._ensure_root()

        target = self._target_path(
            session_id
        )
        self._reject_symlink(target)

        encoded = self._encode_state(
            state
        )

        temp_path: Path | None = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=self.root,
                prefix=f".{self._storage_key(session_id)}.",
                suffix=".tmp",
                delete=False,
            ) as temp_file:
                temp_path = Path(
                    temp_file.name
                )

                if os.name != "nt":
                    os.chmod(
                        temp_path,
                        0o600,
                    )

                temp_file.write(
                    encoded
                )
                temp_file.flush()
                os.fsync(
                    temp_file.fileno()
                )

            self._reject_symlink(target)

            os.replace(
                temp_path,
                target,
            )

        except SessionStorageError:
            raise
        except OSError as exc:
            raise SessionStorageError(
                "Não foi possível persistir a Session atomicamente."
            ) from exc
        finally:
            if (
                temp_path is not None
                and temp_path.exists()
            ):
                try:
                    temp_path.unlink()
                except OSError:
                    pass

    @staticmethod
    def _read_state_file(
        path: Path,
    ) -> dict[str, Any]:
        JsonSessionStateStore._reject_symlink(
            path
        )

        try:
            raw_bytes = path.read_bytes()
        except OSError as exc:
            raise SessionStorageError(
                "Não foi possível ler o estado persistido da Session."
            ) from exc

        try:
            raw_text = raw_bytes.decode(
                "utf-8"
            )
        except UnicodeDecodeError as exc:
            raise SessionCorruptStateError(
                "O estado persistido da Session não contém UTF-8 válido."
            ) from exc

        try:
            state = json.loads(
                raw_text
            )
        except json.JSONDecodeError as exc:
            raise SessionCorruptStateError(
                "O estado persistido da Session contém JSON inválido."
            ) from exc

        if not isinstance(
            state,
            dict,
        ):
            raise SessionCorruptStateError(
                "O estado persistido da Session deve possuir objeto JSON na raiz."
            )

        return state

    def load(
        self,
        *,
        session_id: str,
    ) -> dict[str, Any]:
        if not self._existing_root():
            raise SessionNotFoundError(
                f"Session não encontrada: {session_id}."
            )

        target = self._target_path(
            session_id
        )
        self._reject_symlink(target)

        try:
            if not target.exists():
                raise SessionNotFoundError(
                    f"Session não encontrada: {session_id}."
                )
        except OSError as exc:
            raise SessionStorageError(
                "Não foi possível localizar a Session persistida."
            ) from exc

        return self._read_state_file(
            target
        )

    def list_session_ids(
        self,
    ) -> tuple[str, ...]:
        if not self._existing_root():
            return ()

        try:
            candidates = sorted(
                path
                for path in self.root.iterdir()
                if path.suffix == ".json"
            )
        except OSError as exc:
            raise SessionStorageError(
                "Não foi possível listar as Sessions persistidas."
            ) from exc

        session_ids: list[str] = []

        for path in candidates:
            state = self._read_state_file(
                path
            )

            session_id = state.get(
                "session_id"
            )

            if not isinstance(
                session_id,
                str,
            ):
                raise SessionCorruptStateError(
                    "O estado persistido não contém session_id válido."
                )

            expected_name = (
                f"{self._storage_key(session_id)}.json"
            )

            if path.name != expected_name:
                raise SessionCorruptStateError(
                    "O filename persistido não corresponde à identidade da Session."
                )

            session_ids.append(
                session_id
            )

        return tuple(
            sorted(session_ids)
        )

    def purge(
        self,
        *,
        session_id: str,
    ) -> None:
        if not self._existing_root():
            raise SessionNotFoundError(
                f"Session não encontrada: {session_id}."
            )

        target = self._target_path(
            session_id
        )
        self._reject_symlink(target)

        try:
            if not target.exists():
                raise SessionNotFoundError(
                    f"Session não encontrada: {session_id}."
                )

            target.unlink()
        except SessionNotFoundError:
            raise
        except OSError as exc:
            raise SessionStorageError(
                "Não foi possível remover o estado persistido da Session."
            ) from exc
