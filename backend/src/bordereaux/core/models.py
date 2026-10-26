"""Shared enums used across modules.

These are value vocabularies, not business entities. Every enum here is a
``str`` enum so it can be stored directly in a ``String`` column guarded by a
``CheckConstraint`` (no native DB ENUM types - see DATA_MODEL.md §4.1, and
iteration 1 targets SQLite).
"""

from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    """str-valued enum whose ``str()`` is the raw value."""

    def __str__(self) -> str:  # pragma: no cover - trivial
        return str(self.value)

    @classmethod
    def values(cls) -> list[str]:
        return [m.value for m in cls]


# --- Actors / audit --------------------------------------------------------


class ActorType(StrEnum):
    USER = "USER"
    SYSTEM = "SYSTEM"
    AI = "AI"


class AuditAction(StrEnum):
    CREATE = "CREATE"
    READ = "READ"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    EXECUTE = "EXECUTE"


class UserRole(StrEnum):
    ADMIN = "admin"
    PROJECT_OWNER = "project_owner"
    ANALYST = "analyst"
    REVIEWER = "reviewer"
    VIEWER = "viewer"


# --- Jobs (ADR-006) --------------------------------------------------------


class JobStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

    @property
    def is_terminal(self) -> bool:
        return self in (JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED)


class JobType(StrEnum):
    # From DATA_MODEL.md §3.13
    PARSE = "PARSE"
    PROFILE = "PROFILE"
    GENERATE_MAPPINGS = "GENERATE_MAPPINGS"
    STANDARDIZE = "STANDARDIZE"
    RECONCILE = "RECONCILE"
    REPORT = "REPORT"
    # Added for the Bordereaux Processing Accelerator workflow
    VALIDATE = "VALIDATE"
    CLEAN = "CLEAN"
    FINANCIAL_CHECKS = "FINANCIAL_CHECKS"
    EXPORT = "EXPORT"


# --- Projects / assets -----------------------------------------------------


class ProjectStatus(StrEnum):
    CREATED = "CREATED"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    DELETED = "DELETED"


class SourceAssetStatus(StrEnum):
    UPLOADED = "UPLOADED"
    PARSING = "PARSING"
    PARSED = "PARSED"
    FAILED = "FAILED"
    DELETED = "DELETED"


class FileFormat(StrEnum):
    CSV = "CSV"
    TSV = "TSV"
    XLSX = "XLSX"
    XLS = "XLS"
    JSON = "JSON"
    JSONL = "JSONL"
    PARQUET = "PARQUET"


class SourceVersionStatus(StrEnum):
    PARSED = "PARSED"
    PROFILED = "PROFILED"
    MAPPED = "MAPPED"
    STANDARDIZED = "STANDARDIZED"
    FAILED = "FAILED"


class DataType(StrEnum):
    STRING = "STRING"
    INTEGER = "INTEGER"
    DECIMAL = "DECIMAL"
    BOOLEAN = "BOOLEAN"
    DATE = "DATE"
    DATETIME = "DATETIME"
    UNKNOWN = "UNKNOWN"


# --- Schemas / mappings ----------------------------------------------------


class SchemaStandard(StrEnum):
    ACORD = "ACORD"
    CUSTOM = "CUSTOM"
    PROPRIETARY = "PROPRIETARY"


class MappingSetStatus(StrEnum):
    DRAFT = "DRAFT"
    FINALIZED = "FINALIZED"
    SUPERSEDED = "SUPERSEDED"


class MappingCandidateStatus(StrEnum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


class MappingOrigin(StrEnum):
    APPROVED = "APPROVED"
    MANUAL = "MANUAL"
    AUTO_APPROVED = "AUTO_APPROVED"


# --- Processing run workflow (new for iteration 1) -------------------------


class ProcessingRunStatus(StrEnum):
    """The 14 run states. Transition rules live in the runs state machine
    (owned by the coordinator), NOT here - this is just the vocabulary."""

    STARTED = "STARTED"
    FILE_UPLOADED = "FILE_UPLOADED"
    FILE_VALIDATED = "FILE_VALIDATED"
    CLEANING_COMPLETED = "CLEANING_COMPLETED"
    CLEANING_REVIEW_PENDING = "CLEANING_REVIEW_PENDING"
    MAPPING_REVIEW_PENDING = "MAPPING_REVIEW_PENDING"
    MAPPING_CONFIRMED = "MAPPING_CONFIRMED"
    TREATY_FIGURES_PENDING = "TREATY_FIGURES_PENDING"
    TREATY_FIGURES_VALIDATED = "TREATY_FIGURES_VALIDATED"
    FINANCIAL_CHECKS_COMPLETED = "FINANCIAL_CHECKS_COMPLETED"
    DISCREPANCY_REVIEW_PENDING = "DISCREPANCY_REVIEW_PENDING"
    REPORT_GENERATION_PENDING = "REPORT_GENERATION_PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class CleaningResultStatus(StrEnum):
    PENDING_REVIEW = "PENDING_REVIEW"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RETRIED = "RETRIED"


class ResolutionStage(StrEnum):
    EXACT = "EXACT"
    FUZZY = "FUZZY"
    SEMANTIC_ARITHMETIC = "SEMANTIC_ARITHMETIC"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    UNRESOLVED = "UNRESOLVED"


class DiscrepancyCategory(StrEnum):
    CORE_DEDUCTION = "CORE_DEDUCTION"
    TREATY_RATIO = "TREATY_RATIO"
    BASIS_ALIGNMENT = "BASIS_ALIGNMENT"
    TRAP = "TRAP"
    TOTALS = "TOTALS"
    SIGN = "SIGN"


class Severity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class DiscrepancyStatus(StrEnum):
    CONFIRMED_ERROR = "CONFIRMED_ERROR"
    VALID_DIFFERENCE = "VALID_DIFFERENCE"
    WARNING = "WARNING"
    UNRESOLVED = "UNRESOLVED"
    OVERRIDDEN = "OVERRIDDEN"


class LineageArtifactType(StrEnum):
    # From DATA_MODEL.md §3.15
    CLAIMS_MAPPING_ROW = "claims_mapping_row"
    SUBLEDGER_ROW = "subledger_row"
    VARIANCE_RECORD = "variance_record"
    DIAGNOSTIC_FINDING = "diagnostic_finding"
    # Added for iteration 1
    PROCESSED_ROW = "processed_row"
    DISCREPANCY_FINDING = "discrepancy_finding"
    MONEY_COLUMN_RESOLUTION = "money_column_resolution"
