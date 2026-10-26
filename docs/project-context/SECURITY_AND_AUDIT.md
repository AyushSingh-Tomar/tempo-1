# Security and Audit Specification
## Bordereaux Intelligence Platform

> **Version:** 1.0
> **Date:** 2026-10-09
> **Status:** Approved for MVP

---

## 1. Security Architecture Overview

### 1.1 Security Layers

```
┌─────────────────────────────────────────────────────────────┐
│                    Transport Layer                           │
│                    (TLS 1.2+)                                │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                  Authentication Layer                        │
│            (Token Validation, Session Management)            │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                  Authorization Layer                         │
│              (RBAC, Permission Checks)                       │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    Input Validation                          │
│            (Schema Validation, Sanitization)                 │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    Business Logic                            │
│              (Domain Services, Rules)                        │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                      Data Layer                              │
│        (Encryption at Rest, Access Control)                  │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Trust Boundaries

| Boundary | Trust Level | Controls |
|----------|-------------|----------|
| External → API | Untrusted | Auth, validation, rate limiting |
| API → Services | Authenticated | Authorization checks |
| Services → Database | Trusted | Connection security, least privilege |
| Services → Storage | Trusted | Signed URLs, access control |
| Services → LLM | Untrusted output | Schema validation, content filtering |

---

## 2. Authentication

### 2.1 Authentication Abstraction

```python
class AuthProvider(Protocol):
    """Abstract authentication provider."""
    
    async def validate_token(self, token: str) -> AuthResult:
        """Validate token and return user info."""
        ...
    
    async def get_user(self, user_id: str) -> User | None:
        """Get user by ID."""
        ...


@dataclass
class AuthResult:
    valid: bool
    user_id: str | None
    roles: list[str]
    permissions: list[str]
    expires_at: datetime | None
    error: str | None
```

### 2.2 MVP Authentication (Development)

```python
class DevAuthProvider(AuthProvider):
    """Simple token-based auth for development only."""
    
    # NOT FOR PRODUCTION
    # Tokens are static, stored in environment
    # No session management
    # No token refresh
```

**Development Tokens:**
- Configured via environment variable
- Format: `dev-{user_id}-{role}`
- Example: `dev-analyst1-analyst`

### 2.3 Production Authentication (Future)

```python
class OIDCAuthProvider(AuthProvider):
    """OIDC/OAuth2 authentication."""
    
    # Integrates with enterprise IdP
    # JWT validation
    # Token refresh
    # Session management
```

### 2.4 Authentication Flow

```
Client                    API                     AuthProvider
  │                        │                           │
  │──── Request + Token ──▶│                           │
  │                        │──── Validate Token ──────▶│
  │                        │◀──── AuthResult ─────────│
  │                        │                           │
  │                        │ [If invalid]              │
  │◀──── 401 Unauthorized ─│                           │
  │                        │                           │
  │                        │ [If valid]                │
  │                        │──── Process Request ─────▶│
```

---

## 3. Authorization (RBAC)

### 3.1 Role Definitions

| Role | Description | Typical User |
|------|-------------|--------------|
| `admin` | Full system access | System administrator |
| `project_owner` | Full access to owned projects | Senior analyst |
| `analyst` | Create, process, reconcile | Reinsurance analyst |
| `reviewer` | Review and approve decisions | Senior reviewer |
| `viewer` | Read-only access | Auditor, observer |

### 3.2 Permission Definitions

```python
class Permission(Enum):
    # Project
    PROJECT_CREATE = "project:create"
    PROJECT_READ = "project:read"
    PROJECT_UPDATE = "project:update"
    PROJECT_DELETE = "project:delete"
    
    # Asset
    ASSET_UPLOAD = "asset:upload"
    ASSET_READ = "asset:read"
    ASSET_DELETE = "asset:delete"
    
    # Mapping
    MAPPING_GENERATE = "mapping:generate"
    MAPPING_APPROVE = "mapping:approve"
    MAPPING_REJECT = "mapping:reject"
    MAPPING_MANUAL = "mapping:manual"
    
    # Reconciliation
    RECONCILIATION_CREATE = "reconciliation:create"
    RECONCILIATION_READ = "reconciliation:read"
    
    # Report
    REPORT_GENERATE = "report:generate"
    REPORT_EXPORT = "report:export"
    
    # Treaty (Future)
    TREATY_CREATE = "treaty:create"
    TREATY_UPDATE = "treaty:update"
    TREATY_APPROVE = "treaty:approve"
    
    # Admin
    USER_MANAGE = "user:manage"
    SYSTEM_CONFIG = "system:config"
    AUDIT_READ = "audit:read"
```

### 3.3 Role-Permission Matrix

| Permission | admin | project_owner | analyst | reviewer | viewer |
|------------|:-----:|:-------------:|:-------:|:--------:|:------:|
| project:create | ✓ | ✓ | ✓ | - | - |
| project:read | ✓ | ✓ | ✓ | ✓ | ✓ |
| project:update | ✓ | ✓ | ✓ | - | - |
| project:delete | ✓ | ✓ | - | - | - |
| asset:upload | ✓ | ✓ | ✓ | - | - |
| asset:read | ✓ | ✓ | ✓ | ✓ | ✓ |
| asset:delete | ✓ | ✓ | - | - | - |
| mapping:generate | ✓ | ✓ | ✓ | - | - |
| mapping:approve | ✓ | ✓ | - | ✓ | - |
| mapping:reject | ✓ | ✓ | - | ✓ | - |
| mapping:manual | ✓ | ✓ | ✓ | - | - |
| reconciliation:create | ✓ | ✓ | ✓ | - | - |
| reconciliation:read | ✓ | ✓ | ✓ | ✓ | ✓ |
| report:generate | ✓ | ✓ | ✓ | ✓ | - |
| report:export | ✓ | ✓ | ✓ | ✓ | ✓ |
| audit:read | ✓ | - | - | - | - |
| user:manage | ✓ | - | - | - | - |
| system:config | ✓ | - | - | - | - |

### 3.4 Resource-Level Authorization

Beyond role permissions, resource ownership is checked:

```python
async def check_project_access(
    user: User,
    project: Project,
    permission: Permission
) -> bool:
    # Admin has full access
    if "admin" in user.roles:
        return True
    
    # Check role permission
    if permission not in get_role_permissions(user.roles):
        return False
    
    # Check resource ownership/membership
    if project.owner_id == user.id:
        return True
    
    if user.id in project.member_ids:
        return True
    
    return False
```

### 3.5 Authorization Middleware

```python
def require_permission(permission: Permission):
    """Decorator for endpoint authorization."""
    
    async def middleware(request: Request, call_next):
        user = request.state.user
        
        # Get resource from request if applicable
        project_id = request.path_params.get("project_id")
        
        if project_id:
            project = await get_project(project_id)
            authorized = await check_project_access(
                user, project, permission
            )
        else:
            authorized = permission in get_role_permissions(user.roles)
        
        if not authorized:
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied: {permission.value}"
            )
        
        return await call_next(request)
    
    return middleware
```

---

## 4. Data Protection

### 4.1 Data Classification

| Classification | Description | Examples |
|----------------|-------------|----------|
| **Public** | No restrictions | Schema definitions, documentation |
| **Internal** | Authenticated access | Project names, job status |
| **Confidential** | Role-based access | Claims data, financial values |
| **Sensitive** | Strict controls | PII if present, credentials |

### 4.2 Encryption at Rest

**Database:**
- PostgreSQL with TDE (Transparent Data Encryption) if available
- Or application-level encryption for sensitive columns

**Object Storage:**
- Server-side encryption (SSE-S3 or SSE-KMS)
- Or client-side encryption before upload

### 4.3 Encryption in Transit

- TLS 1.2+ required for all connections
- Certificate validation enforced
- No mixed content allowed

### 4.4 PII Handling

**Detection:**
- Column-level metadata flags for PII
- Pattern detection for common PII (email, phone, SSN)

**Protection:**
- PII columns excluded from LLM context by default
- Masking/redaction available for reports
- Audit logging for PII access

### 4.5 LLM Data Protection

```python
class EvidenceRedactor:
    """Redact sensitive data before LLM calls."""
    
    def redact(self, data: dict) -> dict:
        """Apply redaction rules."""
        
        for field in self.pii_fields:
            if field in data:
                data[field] = self.mask(data[field])
        
        for field in self.financial_fields:
            if field in data:
                data[field] = self.pseudonymize(data[field])
        
        return data
    
    def mask(self, value: str) -> str:
        """Mask PII values."""
        # "john.doe@example.com" → "j***@e***.com"
        ...
    
    def pseudonymize(self, value: str) -> str:
        """Deterministic pseudonymization."""
        # Preserves relationships while hiding values
        return hmac_sha256(self.secret_key, value)[:16]
```

---

## 5. Audit System

### 5.1 Audit Event Model

```python
@dataclass
class AuditEvent:
    id: UUID
    timestamp: datetime
    
    # Actor
    actor_id: UUID | None
    actor_type: ActorType  # USER, SYSTEM, AI
    actor_ip: str | None
    actor_user_agent: str | None
    
    # Action
    event_type: str  # e.g., "mapping.approved"
    action: str  # CREATE, READ, UPDATE, DELETE, APPROVE, REJECT, EXECUTE
    
    # Target
    target_type: str  # e.g., "CandidateMapping"
    target_id: UUID
    
    # Context
    project_id: UUID | None
    request_id: str | None
    
    # State
    before_state: dict | None
    after_state: dict | None
    
    # Details
    reason: str | None
    metadata: dict
```

### 5.2 Event Type Catalog

#### Project Events
| Event Type | Action | Description |
|------------|--------|-------------|
| `project.created` | CREATE | Project created |
| `project.updated` | UPDATE | Project metadata updated |
| `project.archived` | UPDATE | Project archived |
| `project.deleted` | DELETE | Project deleted |

#### Asset Events
| Event Type | Action | Description |
|------------|--------|-------------|
| `asset.uploaded` | CREATE | File uploaded |
| `asset.parsed` | EXECUTE | File parsing completed |
| `asset.deleted` | DELETE | Asset deleted |

#### Mapping Events
| Event Type | Action | Description |
|------------|--------|-------------|
| `mapping.candidates_generated` | CREATE | Candidates generated |
| `mapping.approved` | APPROVE | Mapping approved |
| `mapping.rejected` | REJECT | Mapping rejected |
| `mapping.manual_created` | CREATE | Manual mapping created |
| `mapping.finalized` | UPDATE | Mapping set finalized |

#### Reconciliation Events
| Event Type | Action | Description |
|------------|--------|-------------|
| `reconciliation.created` | CREATE | Run created |
| `reconciliation.started` | EXECUTE | Run started |
| `reconciliation.completed` | EXECUTE | Run completed |
| `reconciliation.failed` | EXECUTE | Run failed |

#### Review Events
| Event Type | Action | Description |
|------------|--------|-------------|
| `review.decision_made` | CREATE | Review decision recorded |

#### Treaty Events (Future)
| Event Type | Action | Description |
|------------|--------|-------------|
| `treaty.state_created` | CREATE | Treaty state created |
| `treaty.state_approved` | APPROVE | Treaty state approved |
| `treaty.state_rolled_back` | UPDATE | Rollback executed |

#### System Events
| Event Type | Action | Description |
|------------|--------|-------------|
| `auth.login` | CREATE | User login |
| `auth.logout` | DELETE | User logout |
| `auth.permission_denied` | READ | Permission denied |
| `system.config_changed` | UPDATE | System config changed |

### 5.3 Audit Storage

**Requirements:**
- Append-only (no updates, no deletes)
- Indexed by target, actor, timestamp, event_type
- Queryable for compliance reporting
- Retention configurable (default: 7 years)

**Schema:**
```sql
CREATE TABLE audit_events (
    id UUID PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    
    actor_id UUID,
    actor_type VARCHAR(20) NOT NULL,
    actor_ip INET,
    actor_user_agent TEXT,
    
    event_type VARCHAR(100) NOT NULL,
    action VARCHAR(20) NOT NULL,
    
    target_type VARCHAR(100) NOT NULL,
    target_id UUID NOT NULL,
    
    project_id UUID,
    request_id VARCHAR(100),
    
    before_state JSONB,
    after_state JSONB,
    
    reason TEXT,
    metadata JSONB DEFAULT '{}'
);

-- Indexes
CREATE INDEX idx_audit_timestamp ON audit_events(timestamp);
CREATE INDEX idx_audit_actor ON audit_events(actor_id);
CREATE INDEX idx_audit_target ON audit_events(target_type, target_id);
CREATE INDEX idx_audit_project ON audit_events(project_id);
CREATE INDEX idx_audit_event_type ON audit_events(event_type);

-- Prevent modifications
REVOKE UPDATE, DELETE ON audit_events FROM PUBLIC;
```

### 5.4 Audit Logging Service

```python
class AuditService:
    """Audit logging service."""
    
    async def log(
        self,
        event_type: str,
        target_type: str,
        target_id: UUID,
        action: str,
        actor_id: UUID | None = None,
        actor_type: ActorType = ActorType.SYSTEM,
        before_state: dict | None = None,
        after_state: dict | None = None,
        reason: str | None = None,
        metadata: dict | None = None
    ) -> AuditEvent:
        """Log an audit event."""
        
        event = AuditEvent(
            id=uuid4(),
            timestamp=datetime.utcnow(),
            actor_id=actor_id,
            actor_type=actor_type,
            actor_ip=self._get_client_ip(),
            actor_user_agent=self._get_user_agent(),
            event_type=event_type,
            action=action,
            target_type=target_type,
            target_id=target_id,
            project_id=self._get_project_context(),
            request_id=self._get_request_id(),
            before_state=before_state,
            after_state=after_state,
            reason=reason,
            metadata=metadata or {}
        )
        
        await self.repository.insert(event)
        return event
```

### 5.5 Audit Query API

```python
async def query_audit(
    target_type: str | None = None,
    target_id: UUID | None = None,
    actor_id: UUID | None = None,
    event_type: str | None = None,
    project_id: UUID | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = 100,
    offset: int = 0
) -> PaginatedResult[AuditEvent]:
    """Query audit events with filters."""
    ...
```

---

## 6. Input Validation

### 6.1 Validation Layers

1. **Transport Layer:** TLS validation
2. **Schema Layer:** Pydantic model validation
3. **Business Layer:** Domain rule validation
4. **Database Layer:** Constraint validation

### 6.2 Pydantic Validation

```python
class CreateProjectRequest(BaseModel):
    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        pattern=r"^[a-zA-Z0-9][a-zA-Z0-9\s\-_]*$"
    )
    description: str | None = Field(
        None,
        max_length=2000
    )
    
    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        # Additional validation
        if v.strip() != v:
            raise ValueError("Name cannot have leading/trailing whitespace")
        return v
```

### 6.3 File Upload Validation

```python
class FileUploadValidator:
    """Validate uploaded files."""
    
    MAX_SIZE = 100 * 1024 * 1024  # 100MB
    ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".json", ".parquet"}
    ALLOWED_MIME_TYPES = {
        "text/csv",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
        "application/json",
        "application/octet-stream"  # Parquet
    }
    
    def validate(self, file: UploadFile) -> ValidationResult:
        errors = []
        
        # Size check
        if file.size > self.MAX_SIZE:
            errors.append(f"File size {file.size} exceeds limit {self.MAX_SIZE}")
        
        # Extension check
        ext = Path(file.filename).suffix.lower()
        if ext not in self.ALLOWED_EXTENSIONS:
            errors.append(f"Extension {ext} not allowed")
        
        # MIME type check
        if file.content_type not in self.ALLOWED_MIME_TYPES:
            errors.append(f"Content type {file.content_type} not allowed")
        
        # Magic bytes check
        magic = self._read_magic_bytes(file)
        if not self._validate_magic(magic, ext):
            errors.append("File content does not match extension")
        
        return ValidationResult(valid=len(errors) == 0, errors=errors)
```

---

## 7. Error Handling Security

### 7.1 Error Information Disclosure

**Principle:** Never expose internal details in error messages.

```python
# Bad - exposes internal details
raise HTTPException(
    status_code=500,
    detail=f"Database error: {str(e)}"  # Leaks DB info
)

# Good - generic message with tracking
logger.error(f"Database error: {e}", extra={"request_id": request_id})
raise HTTPException(
    status_code=500,
    detail="An internal error occurred. Reference: {request_id}"
)
```

### 7.2 Error Response Codes

| Situation | Status | Detail |
|-----------|--------|--------|
| Invalid input | 400 | Specific field errors |
| Unauthenticated | 401 | "Authentication required" |
| Unauthorized | 403 | "Permission denied" (no specifics) |
| Not found | 404 | "Resource not found" |
| Conflict | 409 | "Resource conflict" |
| Rate limited | 429 | "Too many requests" |
| Server error | 500 | "Internal error" + reference |

---

## 8. Secrets Management

### 8.1 Secret Categories

| Category | Examples | Storage |
|----------|----------|---------|
| **Application** | Database password, API keys | Environment variables |
| **User** | Auth tokens | Secure session store |
| **Encryption** | Encryption keys | Key management service |

### 8.2 Environment Variables

```bash
# Database
DATABASE_URL=postgresql://...

# Storage
STORAGE_ENDPOINT=...
STORAGE_ACCESS_KEY=...
STORAGE_SECRET_KEY=...

# LLM
LLM_API_KEY=...

# Encryption
ENCRYPTION_KEY=...

# Auth (Development only)
DEV_AUTH_TOKEN=...
```

### 8.3 Secret Hygiene

- Never log secrets
- Never include in error messages
- Never store in code or config files
- Rotate regularly
- Use vault in production

---

## 9. Security Monitoring

### 9.1 Security Events to Monitor

| Event | Severity | Action |
|-------|----------|--------|
| Failed auth attempts | Medium | Log, rate limit |
| Permission denied | Low | Log |
| Invalid input patterns | Medium | Log, investigate |
| Large data export | Medium | Log |
| Admin actions | High | Log, alert |
| Config changes | High | Log, alert |

### 9.2 Security Metrics

```
security_auth_failures_total{reason}
security_permission_denied_total{permission}
security_rate_limit_hits_total{endpoint}
security_admin_actions_total{action}
```

---

## 10. Compliance Considerations

### 10.1 MVP Compliance Posture

| Area | Status | Notes |
|------|--------|-------|
| Audit trail | Implemented | All state changes logged |
| Access control | Implemented | RBAC enforced |
| Data encryption | Partial | TLS in transit, at-rest TBD |
| PII handling | Implemented | Redaction for LLM |
| Retention | Configurable | Policy enforcement |
| SOC 2 | Not claimed | Foundation in place |
| GDPR | Not claimed | Foundation in place |

### 10.2 Future Compliance Work

- Formal security assessment
- Penetration testing
- SOC 2 Type II preparation
- GDPR data subject rights implementation
- Data residency controls
