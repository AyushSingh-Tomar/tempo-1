"""Storage abstraction (ADR-003: immutable artifacts live behind this interface)."""

from bordereaux.storage.local import LocalStorageService
from bordereaux.storage.service import StorageObject, StorageResult, StorageService

__all__ = ["LocalStorageService", "StorageObject", "StorageResult", "StorageService"]
