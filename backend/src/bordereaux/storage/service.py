"""Storage service contract (MODULE_CONTRACTS.md §2.1)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator, Protocol, runtime_checkable


@dataclass(frozen=True)
class StorageResult:
    path: str
    size_bytes: int
    checksum: str  # SHA-256 hex digest
    content_type: str
    created_at: datetime


@dataclass(frozen=True)
class StorageObject:
    path: str
    size_bytes: int
    last_modified: datetime


@runtime_checkable
class StorageService(Protocol):
    async def upload(
        self,
        path: str,
        data: bytes | AsyncIterator[bytes],
        content_type: str = "application/octet-stream",
        overwrite: bool = False,
    ) -> StorageResult:
        """Write ``data`` at ``path`` (parent folders are created as needed). Objects are
        immutable: different content at an existing path raises ``ConflictError`` unless
        ``overwrite``; identical content is an idempotent no-op."""
        ...

    async def upload_file(
        self,
        path: str,
        local_path: Path,
        content_type: str = "application/octet-stream",
        overwrite: bool = False,
    ) -> StorageResult: ...

    async def download(self, path: str) -> bytes:
        """Return the file contents. Raises NotFoundError if missing."""
        ...

    def download_stream(self, path: str) -> AsyncIterator[bytes]: ...

    async def download_to_file(self, path: str, local_path: Path) -> None: ...

    async def checksum(self, path: str) -> str: ...

    async def verify_checksum(self, path: str, expected: str) -> bool: ...

    async def exists(self, path: str) -> bool: ...

    async def delete(self, path: str) -> None:
        """Delete ``path``. No-op if it does not exist."""
        ...

    async def list_objects(self, prefix: str, max_keys: int = 1000) -> list[StorageObject]: ...

    def get_presigned_url(self, path: str, expires_in: int = 3600, method: str = "GET") -> str: ...

    async def health_check(self) -> bool: ...
