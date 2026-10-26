from __future__ import annotations

import builtins
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from pathlib import PurePosixPath
from uuid import uuid4

import pytest

from bordereaux.config import Settings
from bordereaux.core import exceptions as exc
from bordereaux.core.context import get_request_context, request_context
from bordereaux.core.models import JobStatus, ProcessingRunStatus
from bordereaux.core.utils import envelope, error_envelope, model_snapshot, sha256_hex, to_jsonable, utcnow
from bordereaux.models import Project

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("cls", "parent", "status", "code"),
    [
        (exc.ValidationError, exc.ApplicationError, 400, "VALIDATION_ERROR"),
        (exc.SchemaValidationError, exc.ValidationError, 400, "VALIDATION_ERROR"),
        (exc.BusinessRuleError, exc.ValidationError, 422, "VALIDATION_BUSINESS_RULE"),
        (exc.ConstraintViolationError, exc.ValidationError, 400, "VALIDATION_CONSTRAINT"),
        (exc.AuthError, exc.ApplicationError, 401, "UNAUTHORIZED"),
        (exc.AuthenticationError, exc.AuthError, 401, "UNAUTHORIZED"),
        (exc.AuthorizationError, exc.AuthError, 403, "FORBIDDEN"),
        (exc.ResourceError, exc.ApplicationError, 400, "RESOURCE_ERROR"),
        (exc.NotFoundError, exc.ResourceError, 404, "NOT_FOUND"),
        (exc.ConflictError, exc.ResourceError, 409, "CONFLICT"),
        (exc.StateError, exc.ResourceError, 409, "INVALID_STATE"),
        (exc.ProcessingError, exc.ApplicationError, 422, "PROCESSING_ERROR"),
        (exc.IngestionError, exc.ProcessingError, 422, "PARSE_FAILED"),
        (exc.MappingError, exc.ProcessingError, 422, "MAPPING_ERROR"),
        (exc.ReconciliationError, exc.ProcessingError, 422, "RECONCILIATION_FAILED"),
        (exc.LLMError, exc.ProcessingError, 422, "LLM_ERROR"),
        (exc.SystemError, exc.ApplicationError, 500, "INTERNAL_ERROR"),
        (exc.StorageError, exc.SystemError, 500, "STORAGE_ERROR"),
        (exc.DatabaseError, exc.SystemError, 500, "DATABASE_ERROR"),
        (exc.ExternalServiceError, exc.SystemError, 503, "EXTERNAL_SERVICE_ERROR"),
    ],
)
def test_error_hierarchy(cls, parent, status, code) -> None:
    assert issubclass(cls, parent)
    err = cls()
    assert err.status_code == status and err.code == code
    assert err.to_dict() == {"code": code, "message": err.default_message, "details": []}


def test_error_customisation() -> None:
    e = exc.ConflictError("dup", code="JOB_STILL_RUNNING", details={"job_id": "1"})
    assert e.to_dict() == {"code": "JOB_STILL_RUNNING", "message": "dup", "details": [{"job_id": "1"}]}
    assert str(e) == "dup"
    assert exc.ValidationError(details=[{"a": 1}, {"b": 2}]).details == [{"a": 1}, {"b": 2}]
    assert exc.PlatformSystemError is exc.SystemError
    assert exc.SystemError is not builtins.SystemError  # builtin untouched outside the module
    assert exc.BuiltinSystemError is builtins.SystemError


def test_to_jsonable() -> None:
    class Color(Enum):
        RED = "red"

    u = uuid4()
    dt = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    value = {
        "u": u,
        "dt": dt,
        "d": date(2026, 1, 2),
        "dec": Decimal("0.275"),
        "e": Color.RED,
        "s": JobStatus.RUNNING,
        "p": PurePosixPath("a/b"),
        "t": (1, 2),
        "set": {3},
        "b": b"\x01",
        "n": None,
        "f": 1.5,
        "o": object,
        1: "int-key",
    }
    out = to_jsonable(value)
    json.dumps(out)  # must not raise
    assert out["u"] == str(u) and out["dt"] == dt.isoformat() and out["d"] == "2026-01-02"
    assert out["dec"] == "0.275" and out["e"] == "red" and out["s"] == "RUNNING"
    assert out["t"] == [1, 2] and out["set"] == [3] and out["b"] == "01" and out["1"] == "int-key"


def test_envelopes_and_hash() -> None:
    env = envelope({"x": 1}, request_id="req_1", page=2)
    assert env["data"] == {"x": 1} and env["meta"]["request_id"] == "req_1" and env["meta"]["page"] == 2
    err = error_envelope({"code": "X"}, "req_2")
    assert err["error"] == {"code": "X"} and err["meta"]["request_id"] == "req_2"
    assert sha256_hex(b"") == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    assert utcnow().tzinfo is not None


def test_model_snapshot() -> None:
    uid = uuid4()
    p = Project(id=uuid4(), name="n", created_by=uid, status="ACTIVE")
    snap = model_snapshot(p, exclude={"description"})
    assert snap["created_by"] == str(uid) and snap["status"] == "ACTIVE"
    assert "description" not in snap
    json.dumps(snap)


def test_request_context_overlay() -> None:
    assert get_request_context().request_id is None
    with request_context(request_id="r1"):
        with request_context(client_ip="1.2.3.4"):
            ctx = get_request_context()
            assert ctx.request_id == "r1" and ctx.client_ip == "1.2.3.4"
        assert get_request_context().client_ip is None
    assert get_request_context().request_id is None


def test_settings_parsing(tmp_path) -> None:
    s = Settings(
        _env_file=None,
        dev_auth_tokens=" dev-a-analyst, ,dev-b-viewer ",
        cors_origins="http://a, http://b",
    )
    assert s.dev_auth_token_list == ["dev-a-analyst", "dev-b-viewer"]
    assert s.cors_origin_list == ["http://a", "http://b"]
    assert s.is_sqlite
    assert Settings(_env_file=None).database_url == "sqlite+aiosqlite:///./bordereaux.db"


def test_run_status_vocabulary() -> None:
    assert len(ProcessingRunStatus) == 14
    assert JobStatus.SUCCEEDED.is_terminal and not JobStatus.RUNNING.is_terminal
