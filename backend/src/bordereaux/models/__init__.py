"""SQLAlchemy models. Importing this package registers every table on ``Base.metadata``
(required by Alembic and ``create_all``)."""

from bordereaux.models.base import Base
from bordereaux.models.project import Project, User
from bordereaux.models.job import Job
from bordereaux.models.asset import SourceAsset, SourceVersion
from bordereaux.models.profile import ColumnProfile, DataProfile
from bordereaux.models.schema import CanonicalSchema
from bordereaux.models.mapping import ApprovedMapping, MappingCandidate, MappingSet
from bordereaux.models.treaty import TreatyFigures
from bordereaux.models.run import ProcessingRun
from bordereaux.models.cleaning import CleaningResult
from bordereaux.models.ai import AIInteraction
from bordereaux.models.ai_credential import UserAICredential
from bordereaux.models.money_rules import MoneyColumnResolution, MoneyRelation
from bordereaux.models.discrepancy import DiscrepancyFinding, DiscrepancyOverride
from bordereaux.models.artifact import AuditReportArtifact, PeriodExtractArtifact, ProcessedFileArtifact
from bordereaux.models.format_template import FormatTemplate
from bordereaux.models.audit_event import AuditEvent, LineageRecord
from bordereaux.models.recon import ReconDataset, ReconFile, ReconRun
from bordereaux.models.immutability import AppendOnlyViolation

__all__ = [
    "Base",
    "ReconDataset",
    "ReconFile",
    "ReconRun",
    "User",
    "Project",
    "Job",
    "SourceAsset",
    "SourceVersion",
    "DataProfile",
    "ColumnProfile",
    "CanonicalSchema",
    "MappingSet",
    "MappingCandidate",
    "ApprovedMapping",
    "TreatyFigures",
    "ProcessingRun",
    "CleaningResult",
    "MoneyColumnResolution",
    "MoneyRelation",
    "AIInteraction",
    "UserAICredential",
    "DiscrepancyFinding",
    "DiscrepancyOverride",
    "ProcessedFileArtifact",
    "AuditReportArtifact",
    "PeriodExtractArtifact",
    "FormatTemplate",
    "AuditEvent",
    "LineageRecord",
    "AppendOnlyViolation",
]
