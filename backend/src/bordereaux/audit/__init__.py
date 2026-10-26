"""Append-only audit logging."""

from bordereaux.audit.service import AuditService, AuditServiceProtocol, serialize_audit_event

__all__ = ["AuditService", "AuditServiceProtocol", "serialize_audit_event"]
