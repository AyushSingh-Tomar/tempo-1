"""Application error hierarchy (ARCHITECTURE.md §10.1).

Every error carries a machine-readable ``code`` (API_SPECIFICATION.md §5) and
the HTTP ``status_code`` the API layer should return. ``main.py`` registers a
handler that renders any ``ApplicationError`` as the standard error envelope::

    {"error": {"code": ..., "message": ..., "details": [...]}, "meta": {...}}

Note: ``SystemError`` intentionally mirrors the spec's name and shadows the
Python builtin *inside this module only*. Import it as
``from bordereaux.core.exceptions import SystemError as PlatformSystemError``
(or use the ``PlatformSystemError`` alias) if you also need the builtin.
"""

from __future__ import annotations

import builtins
from typing import Any


class ApplicationError(Exception):
    code: str = "INTERNAL_ERROR"
    status_code: int = 500
    default_message: str = "An internal error occurred"

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        details: list[dict[str, Any]] | dict[str, Any] | None = None,
    ) -> None:
        self.message = message or self.default_message
        if code is not None:
            self.code = code
        if details is None:
            self.details: list[dict[str, Any]] = []
        elif isinstance(details, dict):
            self.details = [details]
        else:
            self.details = list(details)
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "details": self.details}


# --- Validation (400) ----------------------------------------------------------


class ValidationError(ApplicationError):
    code = "VALIDATION_ERROR"
    status_code = 400
    default_message = "Request validation failed"


class SchemaValidationError(ValidationError):
    pass


class BusinessRuleError(ValidationError):
    code = "VALIDATION_BUSINESS_RULE"
    status_code = 422
    default_message = "Business rule violated"


class ConstraintViolationError(ValidationError):
    code = "VALIDATION_CONSTRAINT"
    default_message = "Constraint violated"


# --- Auth (401 / 403) -----------------------------------------------------------


class AuthError(ApplicationError):
    code = "UNAUTHORIZED"
    status_code = 401
    default_message = "Authentication required"


class AuthenticationError(AuthError):
    pass


class AuthorizationError(AuthError):
    code = "FORBIDDEN"
    status_code = 403
    default_message = "Permission denied"


# --- Resource (404 / 409) -------------------------------------------------------


class ResourceError(ApplicationError):
    code = "RESOURCE_ERROR"
    status_code = 400
    default_message = "Resource error"


class NotFoundError(ResourceError):
    code = "NOT_FOUND"
    status_code = 404
    default_message = "Resource not found"


class ConflictError(ResourceError):
    code = "CONFLICT"
    status_code = 409
    default_message = "Resource conflict"


class StateError(ResourceError):
    """Illegal state transition (e.g. job already terminal, run in wrong step)."""

    code = "INVALID_STATE"
    status_code = 409
    default_message = "Operation not allowed in the current state"


# --- Processing (422) ------------------------------------------------------------


class ProcessingError(ApplicationError):
    code = "PROCESSING_ERROR"
    status_code = 422
    default_message = "Processing failed"


class IngestionError(ProcessingError):
    code = "PARSE_FAILED"
    default_message = "Could not parse file"


class MappingError(ProcessingError):
    code = "MAPPING_ERROR"
    default_message = "Mapping failed"


class ReconciliationError(ProcessingError):
    code = "RECONCILIATION_FAILED"
    default_message = "Reconciliation execution failed"


class LLMError(ProcessingError):
    code = "LLM_ERROR"
    default_message = "LLM operation failed"


# --- System (500 / 503) ----------------------------------------------------------


class SystemError(ApplicationError):  # noqa: A001 - name mandated by ARCHITECTURE.md §10.1
    code = "INTERNAL_ERROR"
    status_code = 500
    default_message = "An internal error occurred"


PlatformSystemError = SystemError


class StorageError(SystemError):
    code = "STORAGE_ERROR"
    default_message = "Storage operation failed"


class DatabaseError(SystemError):
    code = "DATABASE_ERROR"
    default_message = "Database operation failed"


class ExternalServiceError(SystemError):
    code = "EXTERNAL_SERVICE_ERROR"
    status_code = 503
    default_message = "External service unavailable"


# Keep a handle on the real builtin for anyone who star-imports this module.
BuiltinSystemError = builtins.SystemError

__all__ = [
    "ApplicationError",
    "ValidationError",
    "SchemaValidationError",
    "BusinessRuleError",
    "ConstraintViolationError",
    "AuthError",
    "AuthenticationError",
    "AuthorizationError",
    "ResourceError",
    "NotFoundError",
    "ConflictError",
    "StateError",
    "ProcessingError",
    "IngestionError",
    "MappingError",
    "ReconciliationError",
    "LLMError",
    "SystemError",
    "PlatformSystemError",
    "StorageError",
    "DatabaseError",
    "ExternalServiceError",
]
