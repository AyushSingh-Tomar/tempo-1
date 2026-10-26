# Test Strategy
## Bordereaux Intelligence Platform

> **Version:** 1.0
> **Date:** 2026-10-09
> **Status:** Approved for MVP

---

## 1. Testing Philosophy

### 1.1 Principles

1. **Test behavior, not implementation** — Tests validate outcomes, not internals
2. **Fast feedback** — Unit tests run in seconds, CI completes in minutes
3. **Deterministic** — Tests produce same results every run
4. **Independent** — Tests don't depend on execution order
5. **Golden dataset validation** — Real-world scenarios verified

### 1.2 Test Pyramid

```
                    /\
                   /  \
                  / E2E\         ← Few, slow, high confidence
                 /______\
                /        \
               /Integration\     ← Moderate, API boundaries
              /____________\
             /              \
            /    Unit Tests  \   ← Many, fast, focused
           /__________________\
```

### 1.3 Coverage Targets

| Layer | Target | Rationale |
|-------|--------|-----------|
| Domain Logic | ≥ 90% | Core business rules must be tested |
| Services | ≥ 85% | Service composition critical |
| API Handlers | ≥ 80% | Input validation and routing |
| Infrastructure | ≥ 70% | Adapters have external dependencies |
| Overall | ≥ 80% | Balance thoroughness and velocity |

---

## 2. Test Categories

### 2.1 Unit Tests

**Scope:** Single function/class in isolation  
**Dependencies:** Mocked  
**Execution:** In-memory, < 100ms each

**What to test:**
- Domain entities and value objects
- Business rule validation
- Pure transformations
- Scoring algorithms
- Variance calculations
- Data type conversions

**Example:**
```python
# test_variance_calculator.py

def test_absolute_variance_calculation():
    result = calculate_variance(
        reported=Decimal("10000"),
        subledger=Decimal("9500")
    )
    assert result.absolute_variance == Decimal("-500")

def test_percentage_variance_with_zero_denominator():
    result = calculate_variance(
        reported=Decimal("100"),
        subledger=Decimal("0")
    )
    assert result.percentage_variance is None
    assert result.absolute_variance == Decimal("100")

def test_within_tolerance_absolute():
    config = VarianceConfig(
        absolute_threshold=Decimal("100"),
        absolute_enabled=True
    )
    result = evaluate_threshold(
        variance=Decimal("50"),
        config=config
    )
    assert result.within_threshold is True
```

### 2.2 Integration Tests

**Scope:** Multiple components working together  
**Dependencies:** Real database (test instance), mocked external services  
**Execution:** Database transactions rolled back, < 1s each

**What to test:**
- API endpoint → Service → Repository flow
- Database operations and transactions
- File storage operations
- Job execution flow
- Cross-module interactions

**Example:**
```python
# test_mapping_service_integration.py

@pytest.mark.integration
async def test_generate_candidates_creates_mappings(
    db_session,
    sample_profile,
    canonical_schema
):
    service = MappingService(db_session)
    
    candidates = await service.generate_candidates(
        version_id=sample_profile.version_id,
        schema_id=canonical_schema.id
    )
    
    assert len(candidates) > 0
    for candidate in candidates:
        assert candidate.confidence.total >= 0
        assert candidate.confidence.total <= 1
        assert candidate.status == MappingStatus.PROPOSED
```

### 2.3 API Tests

**Scope:** HTTP endpoints  
**Dependencies:** Test database, mocked external services  
**Execution:** Full request/response cycle

**What to test:**
- Request validation
- Authentication/authorization
- Response format
- Error handling
- Status codes

**Example:**
```python
# test_project_api.py

@pytest.mark.api
async def test_create_project(client, auth_headers):
    response = await client.post(
        "/api/v1/projects",
        json={"name": "Test Project", "description": "Test"},
        headers=auth_headers
    )
    
    assert response.status_code == 201
    data = response.json()
    assert "id" in data["data"]
    assert data["data"]["name"] == "Test Project"
    assert data["data"]["status"] == "CREATED"

@pytest.mark.api
async def test_create_project_unauthorized(client):
    response = await client.post(
        "/api/v1/projects",
        json={"name": "Test Project"}
    )
    
    assert response.status_code == 401

@pytest.mark.api
async def test_create_project_invalid_name(client, auth_headers):
    response = await client.post(
        "/api/v1/projects",
        json={"name": ""},  # Invalid: empty
        headers=auth_headers
    )
    
    assert response.status_code == 400
    assert "name" in response.json()["error"]["details"][0]["field"]
```

### 2.4 Golden Dataset Tests

**Scope:** End-to-end workflow validation  
**Dependencies:** Synthetic test data with known expected results  
**Execution:** Full pipeline, minutes

**What to test:**
- Complete ingestion → standardization → reconciliation flow
- Expected mapping confidence scores
- Expected variance records
- Expected diagnostic findings
- Lineage correctness

**Example:**
```python
# test_golden_dataset.py

@pytest.mark.golden
async def test_golden_claims_mapping_reconciliation(
    golden_claims_csv,
    golden_subledger_csv,
    expected_results
):
    # Ingest Claims Mapping
    cm_asset = await ingest_file(golden_claims_csv)
    cm_version = await parse_asset(cm_asset.id)
    cm_profile = await profile_version(cm_version.id)
    
    # Generate and approve mappings
    candidates = await generate_candidates(cm_version.id)
    for candidate in candidates:
        if candidate.confidence.total >= 0.9:
            await approve_mapping(candidate.id)
    
    # Standardize
    claims_mapping = await standardize(cm_version.id)
    
    # Ingest Subledger
    sl_asset = await ingest_file(golden_subledger_csv)
    subledger = await create_subledger(sl_asset.id)
    
    # Reconcile
    run = await reconcile(
        claims_mapping_id=claims_mapping.id,
        subledger_id=subledger.id
    )
    
    # Verify results
    assert run.summary.total_groups == expected_results.total_groups
    assert run.summary.matched_groups == expected_results.matched_groups
    assert run.summary.unreconciled_groups == expected_results.unreconciled
    
    # Verify specific variances
    variances = await get_variances(run.id)
    for expected in expected_results.variances:
        actual = find_variance(variances, expected.key)
        assert actual.status == expected.status
        assert actual.absolute_variance == expected.variance
```

### 2.5 Contract Tests

**Scope:** Module interface boundaries  
**Dependencies:** Interface stubs  
**Execution:** Fast

**What to test:**
- Module contracts are satisfied
- Input/output types match contracts
- Error types match contracts

**Example:**
```python
# test_storage_contract.py

class StorageContractTest:
    """Verify storage implementations satisfy contract."""
    
    @pytest.fixture(params=["local", "s3"])
    def storage(self, request) -> StorageService:
        if request.param == "local":
            return LocalStorageService(temp_dir)
        else:
            return S3StorageService(test_bucket)
    
    async def test_upload_returns_result(self, storage):
        result = await storage.upload("test/file.txt", b"content")
        
        assert isinstance(result, StorageResult)
        assert result.path == "test/file.txt"
        assert result.size_bytes == 7
        assert len(result.checksum) == 64  # SHA-256 hex
    
    async def test_download_returns_content(self, storage):
        await storage.upload("test/file.txt", b"content")
        
        data = await storage.download("test/file.txt")
        
        assert data == b"content"
    
    async def test_download_not_found_raises(self, storage):
        with pytest.raises(NotFoundError):
            await storage.download("nonexistent/file.txt")
```

---

## 3. Test Data Strategy

### 3.1 Test Data Categories

| Category | Purpose | Characteristics |
|----------|---------|-----------------|
| **Unit fixtures** | Function-level tests | Minimal, focused |
| **Integration fixtures** | Service tests | Realistic structure |
| **Golden dataset** | E2E validation | Known expected results |
| **Edge case fixtures** | Boundary testing | Unusual/extreme values |
| **Performance fixtures** | Load testing | Large scale |

### 3.2 Golden Dataset Specification

**Claims Mapping Test File: `golden_claims_mapping.csv`**

```csv
CLAIM_NO,POL_REF,TXN_DATE,POST_DATE,GROSS_AMT,COMMISSION,NET_AMT,CURRENCY,STATUS,TXN_TYPE,ACCOUNT,PERIOD
CLM-00001,POL-A001,2026-07-15,2026-07-16,10000.00,1500.00,8500.00,USD,PAID,PREMIUM,ACC-001,2026-Q3
CLM-00002,POL-A002,2026-07-16,2026-07-17,25000.00,3750.00,21250.00,USD,PAID,PREMIUM,ACC-001,2026-Q3
...
```

**Rows:** 1,000  
**Embedded scenarios:**
- 950 normal records
- 20 records missing from subledger
- 10 records with amount differences
- 10 records with rounding differences (< $1)
- 5 records with date differences
- 5 records with status casing differences

**Subledger Test File: `golden_subledger.csv`**

```csv
claim_id,policy_id,transaction_date,amount,currency,status,account_code,period,source_system,posting_date
CLM-00001,POL-A001,2026-07-15,8500.00,USD,paid,ACC-001,2026-Q3,GL,2026-07-16
CLM-00002,POL-A002,2026-07-16,21250.00,USD,paid,ACC-001,2026-Q3,GL,2026-07-17
...
```

**Rows:** 990 (10 fewer + 10 extra)

### 3.3 Expected Results File

```yaml
# golden_expected_results.yaml

reconciliation:
  total_groups: 1000
  matched: 935
  within_tolerance: 15
  unreconciled: 50

variances:
  - key: "CLM-00051"
    reported: 15000.00
    subledger: 14500.00
    status: UNRECONCILED
    reason: "Amount mismatch"
    
  - key: "CLM-00101"
    reported: 5000.00
    subledger: 5000.49
    status: WITHIN_TOLERANCE
    reason: "Rounding"

diagnostics:
  D001:
    expected: true
    message_contains: "Row count difference"
  D003:
    expected: true
    count: 20
  D025:
    expected: true
    count: 10

mappings:
  - source: "CLAIM_NO"
    target: "claim_id"
    min_confidence: 0.95
  - source: "GROSS_AMT"
    target: "gross_amount"
    min_confidence: 0.90
```

### 3.4 Fixture Generation

```python
# conftest.py

@pytest.fixture
def golden_claims_csv(tmp_path) -> Path:
    """Generate golden dataset claims mapping."""
    df = generate_golden_claims(
        n_rows=1000,
        missing_ratio=0.02,
        amount_diff_ratio=0.01,
        rounding_diff_ratio=0.01
    )
    path = tmp_path / "golden_claims_mapping.csv"
    df.to_csv(path, index=False)
    return path

@pytest.fixture
def sample_profile() -> DataProfile:
    """Sample profile for unit tests."""
    return DataProfile(
        id=uuid4(),
        version_id=uuid4(),
        row_count=100,
        column_count=10,
        columns=[
            ColumnProfile(
                name="claim_id",
                position=0,
                data_type=DataType.STRING,
                null_count=0,
                distinct_count=100
            ),
            # ... more columns
        ]
    )
```

---

## 4. Test Environment

### 4.1 Local Development

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=bordereaux --cov-report=html

# Run specific category
pytest -m unit
pytest -m integration
pytest -m golden

# Run with parallel execution
pytest -n auto
```

### 4.2 CI Pipeline

```yaml
# .github/workflows/test.yml

name: Tests

on: [push, pull_request]

jobs:
  unit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -e ".[test]"
      - run: pytest -m unit --cov

  integration:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: test
      redis:
        image: redis:7
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: pip install -e ".[test]"
      - run: pytest -m integration

  golden:
    runs-on: ubuntu-latest
    needs: [unit, integration]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: pip install -e ".[test]"
      - run: pytest -m golden
```

### 4.3 Test Database

```python
# conftest.py

@pytest.fixture(scope="session")
def db_engine():
    """Create test database engine."""
    url = os.getenv("TEST_DATABASE_URL", "postgresql://test:test@localhost/test")
    engine = create_async_engine(url)
    yield engine
    engine.dispose()

@pytest.fixture
async def db_session(db_engine):
    """Create transactional test session."""
    async with db_engine.connect() as conn:
        await conn.begin()
        session = AsyncSession(conn)
        
        yield session
        
        await conn.rollback()
```

---

## 5. Specific Test Plans

### 5.1 Variance Calculation Tests

```python
class TestVarianceCalculation:
    """Test variance calculation edge cases."""
    
    @pytest.mark.parametrize("reported,subledger,expected", [
        (Decimal("100"), Decimal("100"), Decimal("0")),
        (Decimal("100"), Decimal("90"), Decimal("10")),
        (Decimal("100"), Decimal("110"), Decimal("-10")),
        (Decimal("0"), Decimal("0"), Decimal("0")),
        (Decimal("100"), Decimal("0"), Decimal("100")),
        (Decimal("0"), Decimal("100"), Decimal("-100")),
    ])
    def test_absolute_variance(self, reported, subledger, expected):
        result = calculate_variance(reported, subledger)
        assert result.absolute_variance == expected
    
    @pytest.mark.parametrize("reported,subledger,expected", [
        (Decimal("100"), Decimal("100"), Decimal("0")),
        (Decimal("100"), Decimal("90"), Decimal("0.1")),  # 10%
        (Decimal("100"), Decimal("0"), None),  # Zero denominator
    ])
    def test_percentage_variance(self, reported, subledger, expected):
        result = calculate_variance(reported, subledger)
        assert result.percentage_variance == expected
    
    def test_negative_values(self):
        result = calculate_variance(
            reported=Decimal("-100"),
            subledger=Decimal("-90")
        )
        assert result.absolute_variance == Decimal("-10")
```

### 5.2 Mapping Confidence Tests

```python
class TestConfidenceScoring:
    """Test confidence score calculation."""
    
    def test_alias_match_high_confidence(self):
        score = calculate_confidence(
            source_column="CLAIM_NO",
            target_field=CanonicalField(
                name="claim_id",
                aliases=["claim_no", "claim_number"]
            ),
            profile=mock_profile
        )
        assert score.breakdown[EvidenceType.ALIAS_MATCH] > 0.8
    
    def test_type_mismatch_reduces_confidence(self):
        score = calculate_confidence(
            source_column="amount",
            target_field=CanonicalField(
                name="claim_id",
                type=DataType.STRING
            ),
            profile=DataProfile(
                columns=[ColumnProfile(
                    name="amount",
                    data_type=DataType.DECIMAL
                )]
            )
        )
        assert score.breakdown[EvidenceType.TYPE_COMPATIBILITY] < 0.5
    
    def test_weights_sum_to_one(self):
        score = calculate_confidence(...)
        assert sum(score.breakdown.values()) == pytest.approx(1.0)
```

### 5.3 Diagnostic Check Tests

```python
class TestDiagnosticChecks:
    """Test diagnostic check logic."""
    
    def test_d001_row_count_difference(self):
        result = DiagnosticEngine().run_check(
            "D001",
            reported_data=DataFrame({"a": range(100)}),
            subledger_data=DataFrame({"a": range(90)})
        )
        
        assert result.check_id == "D001"
        assert result.category == CheckCategory.STRUCTURAL
        assert result.metrics["reported_rows"] == 100
        assert result.metrics["subledger_rows"] == 90
        assert result.metrics["difference"] == 10
    
    def test_d005_duplicate_keys(self):
        result = DiagnosticEngine().run_check(
            "D005",
            reported_data=DataFrame({
                "claim_id": ["A", "A", "B", "C"]
            })
        )
        
        assert result.check_id == "D005"
        assert result.metrics["duplicate_count"] == 1
        assert "A" in result.evidence
```

---

## 6. Performance Testing

### 6.1 Performance Benchmarks

| Operation | Target | Max |
|-----------|--------|-----|
| Parse 100K row CSV | < 10s | 30s |
| Profile 100K rows | < 30s | 60s |
| Generate candidates (50 columns) | < 60s | 120s |
| Reconcile 1M pairs | < 5min | 10min |
| Report generation | < 30s | 60s |

### 6.2 Performance Test Suite

```python
@pytest.mark.performance
class TestPerformance:
    
    @pytest.mark.timeout(30)
    def test_parse_100k_csv(self, large_csv_100k):
        result = parse_csv(large_csv_100k)
        assert result.row_count == 100_000
    
    @pytest.mark.timeout(60)
    def test_profile_100k_rows(self, parsed_100k_data):
        profile = generate_profile(parsed_100k_data)
        assert profile.row_count == 100_000
    
    @pytest.mark.timeout(300)
    def test_reconcile_1m_pairs(self, reported_1m, subledger_1m):
        result = reconcile(reported_1m, subledger_1m)
        assert result.summary.total_groups >= 900_000
```

---

## 7. Test Reporting

### 7.1 Coverage Reports

- **HTML report** for local review
- **XML report** for CI integration
- **Codecov** for PR coverage checks

### 7.2 Test Results

- JUnit XML for CI systems
- Allure for detailed reporting (optional)
- Slack notifications for failures

### 7.3 Quality Gates

```yaml
# CI quality gates
quality_gates:
  coverage:
    minimum: 80
    fail_on_decrease: true
  
  tests:
    must_pass: true
    golden_required: true
  
  performance:
    must_pass: true
    regression_threshold: 10%  # Max slowdown
```

---

## 8. Test Maintenance

### 8.1 Test Hygiene

- Remove obsolete tests when features change
- Keep test data minimal
- Document non-obvious test scenarios
- Review flaky tests regularly

### 8.2 Test Ownership

| Area | Owner |
|------|-------|
| Unit tests | Feature developer |
| Integration tests | Team |
| Golden dataset | Team lead |
| Performance tests | Platform team |
