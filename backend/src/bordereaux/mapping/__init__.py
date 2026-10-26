"""Mapping module (Step 4-5): resolve source columns to the canonical
bordereaux schema, score confidence per ADR-004, and manage the
approve/reject/manual/finalize workflow."""

from bordereaux.mapping.service import (
    approve_candidate,
    create_manual_mapping,
    finalize_mappings,
    generate_mapping_candidates,
    list_candidates,
    reject_candidate,
)

__all__ = [
    "generate_mapping_candidates",
    "approve_candidate",
    "reject_candidate",
    "create_manual_mapping",
    "finalize_mappings",
    "list_candidates",
]
