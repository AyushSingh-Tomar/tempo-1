"""Local-filesystem storage backend (MODULE_CONTRACTS.md §2.1).

Objects are immutable by default (ADR-003): uploading different bytes to an
existing path raises ``ConflictError`` unless ``overwrite=True``; re-uploading
identical bytes is an idempotent no-op. The root directory and any parent
folders are created on demand, writes go through a temp file + atomic rename so
readers never see partial content, and every key is validated so it cannot
escape the root.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator

from bordereaux.core.exceptions import ConflictError, NotFoundError, StorageError, ValidationError
from bordereaux.storage.service import StorageObject, StorageResult

logger = logging.getLogger(__name__)

DEFAULT_CHUNK_SIZE = 1024 * 1024
_DRIVE_RE = re.compile(r"^[A-Za-z]:")


def normalize_key(path: str) -> str:
    """Validated, forward-slash storage key. Rejects empty, absolute, drive-lettered,
    ``..`` and empty-segment paths."""
    key = str(path).replace("\\", "/").strip()
    if not key:
        raise ValidationError("Storage path must not be empty")
    if key.startswith("/") or _DRIVE_RE.match(key):
        raise ValidationError(f"Storage path must be relative: {path!r}")
    if any(p in ("", ".", "..") for p in key.split("/")):
        raise ValidationError(f"Invalid storage path {path!r}")
    return key


class LocalStorageService:
    def __init__(self, root: Path | str, chunk_size: int = DEFAULT_CHUNK_SIZE) -> None:
        self.root = Path(root).resolve()
        self.chunk_size = chunk_size
        try:
            self.root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise StorageError(f"Cannot create storage root {self.root}: {exc}") from exc

    def _resolve(self, path: str) -> Path:
        full = (self.root / normalize_key(path)).resolve()
        if self.root not in full.parents:
            raise ValidationError(f"Invalid storage path {path!r}")
        return full

    @staticmethod
    def _sha256_of(file: Path, chunk_size: int) -> str:
        digest = hashlib.sha256()
        with file.open("rb") as fh:
            while chunk := fh.read(chunk_size):
                digest.update(chunk)
        return digest.hexdigest()

    # --- writes ---------------------------------------------------------------

    async def upload(
        self,
        path: str,
        data: bytes | AsyncIterator[bytes],
        content_type: str = "application/octet-stream",
        overwrite: bool = False,
    ) -> StorageResult:
        key = normalize_key(path)
        target = self._resolve(key)
        digest = hashlib.sha256()
        size = 0
        tmp: str | None = None
        try:
            await asyncio.to_thread(target.parent.mkdir, parents=True, exist_ok=True)
            fd, tmp = await asyncio.to_thread(tempfile.mkstemp, dir=target.parent, suffix=".tmp")
            with os.fdopen(fd, "wb") as fh:
                if isinstance(data, (bytes, bytearray, memoryview)):
                    chunk = bytes(data)
                    fh.write(chunk)
                    digest.update(chunk)
                    size = len(chunk)
                else:
                    async for chunk in data:
                        fh.write(chunk)
                        digest.update(chunk)
                        size += len(chunk)
            checksum = digest.hexdigest()

            if target.is_dir():
                raise ConflictError(f"A directory already exists at {key!r}")
            if target.is_file() and not overwrite:
                existing = await asyncio.to_thread(self._sha256_of, target, self.chunk_size)
                if existing != checksum:
                    raise ConflictError(
                        f"{key!r} already exists with different content (objects are immutable)",
                        details={"path": key},
                    )
            await asyncio.to_thread(os.replace, tmp, target)
            tmp = None
        except OSError as exc:
            raise StorageError(f"Failed to write {key!r}: {exc}") from exc
        finally:
            if tmp is not None:
                Path(tmp).unlink(missing_ok=True)
        return StorageResult(
            path=key,
            size_bytes=size,
            checksum=checksum,
            content_type=content_type,
            created_at=datetime.now(timezone.utc),
        )

    async def upload_file(
        self,
        path: str,
        local_path: Path,
        content_type: str = "application/octet-stream",
        overwrite: bool = False,
    ) -> StorageResult:
        source = Path(local_path)
        if not source.is_file():
            raise NotFoundError(f"Local file not found: {source}")

        async def chunks() -> AsyncIterator[bytes]:
            with source.open("rb") as fh:
                while chunk := await asyncio.to_thread(fh.read, self.chunk_size):
                    yield chunk

        return await self.upload(path, chunks(), content_type=content_type, overwrite=overwrite)

    # --- reads ----------------------------------------------------------------

    async def download(self, path: str) -> bytes:
        target = self._resolve(path)
        try:
            return await asyncio.to_thread(target.read_bytes)
        except (FileNotFoundError, IsADirectoryError) as exc:
            raise NotFoundError(f"Stored file not found: {path}") from exc
        except OSError as exc:
            raise StorageError(f"Failed to read {path!r}: {exc}") from exc

    async def download_stream(self, path: str) -> AsyncIterator[bytes]:
        target = self._resolve(path)
        if not target.is_file():
            raise NotFoundError(f"Stored file not found: {path}")
        with target.open("rb") as fh:
            while chunk := await asyncio.to_thread(fh.read, self.chunk_size):
                yield chunk

    async def download_to_file(self, path: str, local_path: Path) -> None:
        target = self._resolve(path)
        if not target.is_file():
            raise NotFoundError(f"Stored file not found: {path}")
        dest = Path(local_path)

        def _copy() -> None:
            dest.parent.mkdir(parents=True, exist_ok=True)
            with target.open("rb") as src, dest.open("wb") as out:
                while chunk := src.read(self.chunk_size):
                    out.write(chunk)

        try:
            await asyncio.to_thread(_copy)
        except OSError as exc:
            raise StorageError(f"Failed to copy {path!r} to {dest}: {exc}") from exc

    async def checksum(self, path: str) -> str:
        target = self._resolve(path)
        if not target.is_file():
            raise NotFoundError(f"Stored file not found: {path}")
        return await asyncio.to_thread(self._sha256_of, target, self.chunk_size)

    async def verify_checksum(self, path: str, expected: str) -> bool:
        return (await self.checksum(path)) == expected.strip().lower()

    # --- housekeeping ---------------------------------------------------------

    async def exists(self, path: str) -> bool:
        return await asyncio.to_thread(self._resolve(path).is_file)

    async def delete(self, path: str) -> None:
        try:
            await asyncio.to_thread(self._resolve(path).unlink, True)
        except OSError as exc:
            raise StorageError(f"Failed to delete {path!r}: {exc}") from exc

    async def list_objects(self, prefix: str, max_keys: int = 1000) -> list[StorageObject]:
        def _list() -> list[StorageObject]:
            out: list[StorageObject] = []
            for p in sorted(self.root.rglob("*")):
                if not p.is_file() or p.suffix == ".tmp":
                    continue
                key = p.relative_to(self.root).as_posix()
                if not key.startswith(prefix):
                    continue
                st = p.stat()
                out.append(StorageObject(key, st.st_size, datetime.fromtimestamp(st.st_mtime, tz=timezone.utc)))
                if len(out) >= max_keys:
                    break
            return out

        return await asyncio.to_thread(_list)

    def get_presigned_url(self, path: str, expires_in: int = 3600, method: str = "GET") -> str:
        """A ``file://`` URI: local storage has no signing, so this is only a locator."""
        if method.upper() not in ("GET", "PUT"):
            raise ValidationError(f"Unsupported method {method!r}; use GET or PUT")
        return self._resolve(path).as_uri()

    async def health_check(self) -> bool:
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            return os.access(self.root, os.W_OK)
        except OSError:
            logger.exception("Storage health check failed")
            return False
