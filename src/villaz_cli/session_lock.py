import hashlib
import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


SESSION_LOCK_VERSION = 1


class SessionLockError(Exception):
    """Base error for Session lock operations."""


class SessionInUseError(SessionLockError):
    """Raised when another live owner holds the Session lock."""


class SessionLockOwnershipError(SessionLockError):
    """Raised when a caller tries to release another owner's lock."""


class SessionLockCorruptError(SessionLockError):
    """Raised when persisted lock metadata is corrupt or inconsistent."""


class SessionLockStore(Protocol):
    def acquire(
        self,
        *,
        session_id: str,
        owner_id: str,
        pid: int,
    ) -> None:
        ...

    def release(
        self,
        *,
        session_id: str,
        owner_id: str,
    ) -> None:
        ...


@dataclass(frozen=True, slots=True)
class _LockRecord:
    session_id: str
    owner_id: str
    pid: int


def acquire_session_lock(
    session_id: str,
    *,
    owner_id: str,
    store: SessionLockStore,
) -> None:
    store.acquire(
        session_id=session_id,
        owner_id=owner_id,
        pid=os.getpid(),
    )


def release_session_lock(
    session_id: str,
    *,
    owner_id: str,
    store: SessionLockStore,
) -> None:
    store.release(
        session_id=session_id,
        owner_id=owner_id,
    )


class JsonSessionLockStore:
    def __init__(
        self,
        root: Path,
        *,
        process_exists: Callable[[int], bool] | None = None,
    ) -> None:
        self.root = Path(root)
        self._process_exists = (
            process_exists
            if process_exists is not None
            else self._default_process_exists
        )

    @staticmethod
    def _storage_key(
        session_id: str,
    ) -> str:
        return hashlib.sha256(
            session_id.encode("utf-8")
        ).hexdigest()

    def _lock_path(
        self,
        session_id: str,
    ) -> Path:
        return self.root / (
            f"{self._storage_key(session_id)}.lock"
        )

    def _ensure_root(self) -> None:
        try:
            if self.root.exists():
                if not self.root.is_dir():
                    raise SessionLockError(
                        "O diretório de locks está ocupado por um arquivo."
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
            raise SessionLockError(
                "Não foi possível preparar o diretório de locks."
            ) from exc

    def _root_exists(self) -> bool:
        try:
            if not self.root.exists():
                return False

            if not self.root.is_dir():
                raise SessionLockError(
                    "O diretório de locks está ocupado por um arquivo."
                )

            return True
        except OSError as exc:
            raise SessionLockError(
                "Não foi possível acessar o diretório de locks."
            ) from exc

    @staticmethod
    def _reject_symlink(
        path: Path,
    ) -> None:
        try:
            if path.is_symlink():
                raise SessionLockCorruptError(
                    "O arquivo de lock não pode ser um symlink."
                )
        except OSError as exc:
            raise SessionLockError(
                "Não foi possível validar o arquivo de lock."
            ) from exc

    @staticmethod
    def _default_process_exists(
        pid: int,
    ) -> bool:
        try:
            os.kill(
                pid,
                0,
            )
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError:
            # Conservador: se não conseguimos provar que morreu,
            # tratamos o processo como existente.
            return True

        return True

    @staticmethod
    def _encode_record(
        *,
        session_id: str,
        owner_id: str,
        pid: int,
    ) -> bytes:
        payload = {
            "lock_version": SESSION_LOCK_VERSION,
            "owner_id": owner_id,
            "pid": pid,
            "session_id": session_id,
        }

        serialized = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

        return (
            serialized + "\n"
        ).encode("utf-8")

    @staticmethod
    def _decode_record(
        raw_bytes: bytes,
    ) -> _LockRecord:
        try:
            raw_text = raw_bytes.decode(
                "utf-8"
            )
        except UnicodeDecodeError as exc:
            raise SessionLockCorruptError(
                "O lock não contém UTF-8 válido."
            ) from exc

        try:
            payload = json.loads(
                raw_text
            )
        except json.JSONDecodeError as exc:
            raise SessionLockCorruptError(
                "O lock contém JSON inválido."
            ) from exc

        if not isinstance(
            payload,
            dict,
        ):
            raise SessionLockCorruptError(
                "O lock deve possuir objeto JSON na raiz."
            )

        if payload.get(
            "lock_version"
        ) != SESSION_LOCK_VERSION:
            raise SessionLockCorruptError(
                "O lock possui versão incompatível."
            )

        session_id = payload.get(
            "session_id"
        )
        owner_id = payload.get(
            "owner_id"
        )
        pid = payload.get(
            "pid"
        )

        if not isinstance(
            session_id,
            str,
        ) or not session_id:
            raise SessionLockCorruptError(
                "O lock não contém session_id válido."
            )

        if not isinstance(
            owner_id,
            str,
        ) or not owner_id:
            raise SessionLockCorruptError(
                "O lock não contém owner_id válido."
            )

        if (
            not isinstance(pid, int)
            or isinstance(pid, bool)
            or pid <= 0
        ):
            raise SessionLockCorruptError(
                "O lock não contém pid válido."
            )

        return _LockRecord(
            session_id=session_id,
            owner_id=owner_id,
            pid=pid,
        )

    def _read_lock(
        self,
        path: Path,
    ) -> tuple[_LockRecord, bytes]:
        self._reject_symlink(
            path
        )

        try:
            raw_bytes = path.read_bytes()
        except FileNotFoundError:
            raise
        except OSError as exc:
            raise SessionLockError(
                "Não foi possível ler o lock da Session."
            ) from exc

        record = self._decode_record(
            raw_bytes
        )

        return (
            record,
            raw_bytes,
        )

    def _validate_identity(
        self,
        *,
        path: Path,
        session_id: str,
        record: _LockRecord,
    ) -> None:
        if record.session_id != session_id:
            raise SessionLockCorruptError(
                "O lock não corresponde à identidade da Session."
            )

        expected_name = (
            f"{self._storage_key(session_id)}.lock"
        )

        if path.name != expected_name:
            raise SessionLockCorruptError(
                "O filename do lock não corresponde à Session."
            )

    def _create_lock(
        self,
        *,
        path: Path,
        session_id: str,
        owner_id: str,
        pid: int,
    ) -> None:
        encoded = self._encode_record(
            session_id=session_id,
            owner_id=owner_id,
            pid=pid,
        )

        created = False

        try:
            with path.open(
                "xb"
            ) as lock_file:
                created = True

                if os.name != "nt":
                    os.chmod(
                        path,
                        0o600,
                    )

                lock_file.write(
                    encoded
                )
                lock_file.flush()
                os.fsync(
                    lock_file.fileno()
                )
        except FileExistsError:
            raise
        except OSError as exc:
            if created:
                try:
                    path.unlink()
                except OSError:
                    pass

            raise SessionLockError(
                "Não foi possível criar o lock da Session."
            ) from exc

    def acquire(
        self,
        *,
        session_id: str,
        owner_id: str,
        pid: int,
    ) -> None:
        if not owner_id:
            raise SessionLockError(
                "owner_id não pode ser vazio."
            )

        if pid <= 0:
            raise SessionLockError(
                "pid deve ser positivo."
            )

        self._ensure_root()

        path = self._lock_path(
            session_id
        )

        while True:
            self._reject_symlink(
                path
            )

            try:
                self._create_lock(
                    path=path,
                    session_id=session_id,
                    owner_id=owner_id,
                    pid=pid,
                )
                return

            except FileExistsError:
                pass

            try:
                record, observed_bytes = self._read_lock(
                    path
                )
            except FileNotFoundError:
                continue

            self._validate_identity(
                path=path,
                session_id=session_id,
                record=record,
            )

            if record.owner_id == owner_id:
                return

            if self._process_exists(
                record.pid
            ):
                raise SessionInUseError(
                    "A Session já está em uso por outro owner."
                )

            # O owner anterior não existe. Antes de remover,
            # confirmamos que o lock observado continua igual.
            try:
                current_bytes = path.read_bytes()
            except FileNotFoundError:
                continue
            except OSError as exc:
                raise SessionLockError(
                    "Não foi possível confirmar o stale lock."
                ) from exc

            if current_bytes != observed_bytes:
                continue

            self._reject_symlink(
                path
            )

            try:
                path.unlink()
            except FileNotFoundError:
                continue
            except OSError as exc:
                raise SessionLockError(
                    "Não foi possível remover o stale lock."
                ) from exc

    def release(
        self,
        *,
        session_id: str,
        owner_id: str,
    ) -> None:
        if not self._root_exists():
            return

        path = self._lock_path(
            session_id
        )

        while True:
            self._reject_symlink(
                path
            )

            try:
                record, observed_bytes = self._read_lock(
                    path
                )
            except FileNotFoundError:
                return

            self._validate_identity(
                path=path,
                session_id=session_id,
                record=record,
            )

            if record.owner_id != owner_id:
                raise SessionLockOwnershipError(
                    "O lock pertence a outro owner."
                )

            try:
                current_bytes = path.read_bytes()
            except FileNotFoundError:
                return
            except OSError as exc:
                raise SessionLockError(
                    "Não foi possível confirmar a ownership do lock."
                ) from exc

            if current_bytes != observed_bytes:
                continue

            self._reject_symlink(
                path
            )

            try:
                path.unlink()
                return
            except FileNotFoundError:
                return
            except OSError as exc:
                raise SessionLockError(
                    "Não foi possível liberar o lock da Session."
                ) from exc
