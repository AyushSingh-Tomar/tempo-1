"""canonical_schemas, mapping_sets, mapping_candidates, approved_mappings (DATA_MODEL.md §3.6, §3.8)

Revision ID: 005
Revises: 004
Create Date: 2026-10-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from bordereaux.models.types import ExactDecimal

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "canonical_schemas",
        sa.Column("id", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("standard", sa.String(50), nullable=False, server_default="CUSTOM"),
        sa.Column("definition", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_canonical_schemas")),
        sa.CheckConstraint(
            "standard IN ('ACORD', 'CUSTOM', 'PROPRIETARY')", name=op.f("ck_canonical_schemas_standard")
        ),
    )

    op.create_table(
        "mapping_sets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("schema_id", sa.String(100), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="DRAFT"),
        sa.Column("coverage_required", ExactDecimal(5, 4), nullable=True),
        sa.Column("coverage_optional", ExactDecimal(5, 4), nullable=True),
        sa.Column("generation_job_id", sa.Uuid(), nullable=True),
        sa.Column("finalized_by", sa.Uuid(), nullable=True),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mapping_sets")),
        sa.ForeignKeyConstraint(["version_id"], ["source_versions.id"], name=op.f("fk_mapping_sets_version_id_source_versions")),
        sa.ForeignKeyConstraint(["schema_id"], ["canonical_schemas.id"], name=op.f("fk_mapping_sets_schema_id_canonical_schemas")),
        sa.ForeignKeyConstraint(["generation_job_id"], ["jobs.id"], name=op.f("fk_mapping_sets_generation_job_id_jobs")),
        sa.ForeignKeyConstraint(["finalized_by"], ["users.id"], name=op.f("fk_mapping_sets_finalized_by_users")),
        sa.CheckConstraint("status IN ('DRAFT', 'FINALIZED', 'SUPERSEDED')", name=op.f("ck_mapping_sets_status")),
    )
    op.create_index(op.f("ix_mapping_sets_version_id"), "mapping_sets", ["version_id"])
    op.create_index(op.f("ix_mapping_sets_status"), "mapping_sets", ["status"])
    op.create_index(op.f("ix_mapping_sets_schema_id"), "mapping_sets", ["schema_id"])
    op.create_index(op.f("ix_mapping_sets_generation_job_id"), "mapping_sets", ["generation_job_id"])

    op.create_table(
        "mapping_candidates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("mapping_set_id", sa.Uuid(), nullable=False),
        sa.Column("source_column", sa.String(255), nullable=False),
        sa.Column("target_field", sa.String(255), nullable=False),
        sa.Column("confidence_total", ExactDecimal(5, 4), nullable=False),
        sa.Column("confidence_breakdown", sa.JSON(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="PROPOSED"),
        sa.Column("auto_approve_eligible", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mapping_candidates")),
        sa.ForeignKeyConstraint(["mapping_set_id"], ["mapping_sets.id"], name=op.f("fk_mapping_candidates_mapping_set_id_mapping_sets")),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], name=op.f("fk_mapping_candidates_reviewed_by_users")),
        sa.CheckConstraint(
            "status IN ('PROPOSED', 'APPROVED', 'REJECTED', 'SUPERSEDED')", name=op.f("ck_mapping_candidates_status")
        ),
    )
    op.create_index(op.f("ix_mapping_candidates_set_id"), "mapping_candidates", ["mapping_set_id"])
    op.create_index(op.f("ix_mapping_candidates_status"), "mapping_candidates", ["status"])
    op.create_index(op.f("ix_mapping_candidates_source"), "mapping_candidates", ["source_column"])
    op.create_index(op.f("ix_mapping_candidates_confidence"), "mapping_candidates", ["confidence_total"])

    op.create_table(
        "approved_mappings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("mapping_set_id", sa.Uuid(), nullable=False),
        sa.Column("source_column", sa.String(255), nullable=False),
        sa.Column("target_field", sa.String(255), nullable=False),
        sa.Column("origin", sa.String(50), nullable=False),
        sa.Column("confidence_total", ExactDecimal(5, 4), nullable=False),
        sa.Column("transformation", sa.JSON(), nullable=True),
        sa.Column("candidate_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_approved_mappings")),
        sa.ForeignKeyConstraint(["mapping_set_id"], ["mapping_sets.id"], name=op.f("fk_approved_mappings_mapping_set_id_mapping_sets")),
        sa.ForeignKeyConstraint(["candidate_id"], ["mapping_candidates.id"], name=op.f("fk_approved_mappings_candidate_id_mapping_candidates")),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=op.f("fk_approved_mappings_created_by_users")),
        sa.UniqueConstraint("mapping_set_id", "source_column", name=op.f("uq_approved_mappings_source")),
        sa.CheckConstraint(
            "origin IN ('APPROVED', 'MANUAL', 'AUTO_APPROVED')", name=op.f("ck_approved_mappings_origin")
        ),
    )
    op.create_index(op.f("ix_approved_mappings_set_id"), "approved_mappings", ["mapping_set_id"])
    op.create_index(op.f("ix_approved_mappings_candidate_id"), "approved_mappings", ["candidate_id"])


def downgrade() -> None:
    op.drop_table("approved_mappings")
    op.drop_table("mapping_candidates")
    op.drop_table("mapping_sets")
    op.drop_table("canonical_schemas")
