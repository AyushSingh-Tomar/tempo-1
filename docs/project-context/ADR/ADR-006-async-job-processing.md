# ADR-006: Async Job Processing

## Status
**Accepted**

## Date
2026-10-09

## Context

Several operations in the platform are long-running:
- File parsing (seconds to minutes)
- Data profiling (seconds)
- Mapping generation (seconds)
- Standardization (seconds to minutes)
- Reconciliation (minutes)
- Report generation (seconds)

### Requirements

- Non-blocking API responses
- Real-time progress updates
- Job cancellation support
- Failure recovery
- Concurrent job limits per project

## Decision

Implement **async job processing** using database-backed job queue with worker processes.

### Job Flow

```
Client                 API                    Database              Worker
  │                     │                        │                    │
  ├─POST /reconcile────►│                        │                    │
  │                     ├─Create job (PENDING)──►│                    │
  │                     │◄──────────────────────┤                    │
  │◄─202 {job_id}───────┤                        │                    │
  │                     │                        │◄─Poll for jobs─────┤
  │                     │                        ├─Claim job──────────►│
  │                     │                        │                    ├─Update RUNNING
  │                     │                        │◄───────────────────┤
  │─GET /jobs/{id}─────►│                        │                    │
  │                     ├─Query job status──────►│                    │
  │◄─{status:RUNNING}───┤◄──────────────────────┤                    │
  │                     │                        │                    │
  │                     │                        │                    ├─Process...
  │                     │                        │                    │
  │                     │                        │◄─Update progress───┤
  │─GET /jobs/{id}─────►│                        │                    │
  │◄─{status:RUNNING,   │                        │                    │
  │   progress:60%}─────┤                        │                    │
  │                     │                        │                    │
  │                     │                        │◄─Update SUCCEEDED──┤
  │─GET /jobs/{id}─────►│                        │                    │
  │◄─{status:SUCCEEDED} ┤                        │                    │
```

### Job Model

```python
class Job:
    id: UUID
    type: JobType  # PARSE, PROFILE, GENERATE_MAPPINGS, STANDARDIZE, RECONCILE
    status: JobStatus  # PENDING, RUNNING, SUCCEEDED, FAILED, CANCELLED
    project_id: UUID
    input: dict  # Job-specific input parameters
    output: Optional[dict]  # Result on success
    progress: JobProgress
    error: Optional[JobError]
    created_by: UUID
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    
class JobProgress:
    current_step: str
    total_steps: int
    percentage: int
    message: Optional[str]

class JobError:
    code: str
    message: str
    details: Optional[dict]
    traceback: Optional[str]
```

### Worker Implementation

```python
class JobWorker:
    """Process jobs from queue."""
    
    def __init__(self, handlers: dict[JobType, JobHandler]):
        self.handlers = handlers
        self.running = True
    
    async def run(self):
        while self.running:
            job = await self.claim_next_job()
            if job:
                await self.execute(job)
            else:
                await asyncio.sleep(1)  # Poll interval
    
    async def claim_next_job(self) -> Optional[Job]:
        """Atomically claim a pending job."""
        return await self.repo.claim_job(
            types=list(self.handlers.keys()),
            worker_id=self.worker_id
        )
    
    async def execute(self, job: Job):
        handler = self.handlers[job.type]
        try:
            await self.repo.update_status(job.id, JobStatus.RUNNING)
            result = await handler.execute(job, self.progress_callback)
            await self.repo.complete_job(job.id, result)
        except Exception as e:
            await self.repo.fail_job(job.id, e)
```

### Job Handlers

```python
class ReconciliationJobHandler(JobHandler):
    """Handle reconciliation jobs."""
    
    async def execute(
        self, 
        job: Job, 
        progress: ProgressCallback
    ) -> dict:
        config = ReconciliationConfig.model_validate(job.input)
        
        await progress(step="loading_data", percentage=10)
        claims_mapping = await self.load_claims_mapping(config.claims_mapping_id)
        subledger = await self.load_subledger(config.subledger_id)
        
        await progress(step="creating_pivots", percentage=30)
        pivots = await self.create_pivots(claims_mapping, subledger, config)
        
        await progress(step="calculating_variance", percentage=50)
        variances = await self.calculate_variances(pivots, config)
        
        await progress(step="running_diagnostics", percentage=80)
        diagnostics = await self.run_diagnostics(variances, config)
        
        await progress(step="saving_results", percentage=95)
        run = await self.save_results(variances, diagnostics)
        
        return {"reconciliation_id": str(run.id)}
```

### Concurrency Control

```python
async def create_job(project_id: UUID, job_type: JobType) -> Job:
    # Check concurrent job limit
    running_count = await repo.count_running_jobs(project_id)
    if running_count >= MAX_CONCURRENT_JOBS_PER_PROJECT:
        raise ConcurrencyLimitError(
            f"Maximum {MAX_CONCURRENT_JOBS_PER_PROJECT} concurrent jobs"
        )
    
    return await repo.create_job(...)
```

### API Endpoints

```python
@router.post("/reconciliations", status_code=202)
async def create_reconciliation(request: CreateReconciliationRequest):
    job = await job_service.create(
        type=JobType.RECONCILE,
        input=request.model_dump()
    )
    return {"job_id": job.id, "reconciliation_id": job.output.get("reconciliation_id")}

@router.get("/jobs/{job_id}")
async def get_job_status(job_id: UUID):
    job = await job_service.get(job_id)
    return JobResponse(
        id=job.id,
        type=job.type,
        status=job.status,
        progress=job.progress,
        error=job.error,
        started_at=job.started_at,
        completed_at=job.completed_at
    )
```

### Progress Updates (MVP: Polling)

```typescript
// Frontend polling
async function pollJobStatus(jobId: string): Promise<JobStatus> {
  while (true) {
    const response = await fetch(`/api/v1/jobs/${jobId}`);
    const job = await response.json();
    
    updateProgressUI(job.progress);
    
    if (job.status === 'SUCCEEDED' || job.status === 'FAILED') {
      return job;
    }
    
    await sleep(2000);  // Poll every 2 seconds
  }
}
```

### Post-MVP: WebSocket Updates

```python
# Server-sent events for real-time updates
@router.get("/jobs/{job_id}/stream")
async def stream_job_progress(job_id: UUID):
    async def event_generator():
        while True:
            job = await job_service.get(job_id)
            yield f"data: {job.model_dump_json()}\n\n"
            if job.status in (JobStatus.SUCCEEDED, JobStatus.FAILED):
                break
            await asyncio.sleep(1)
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

## Consequences

### Positive

- **Non-blocking** — API returns immediately
- **Visibility** — Real-time progress tracking
- **Scalable** — Multiple workers can process jobs
- **Recoverable** — Failed jobs can be retried
- **Controllable** — Jobs can be cancelled

### Negative

- **Complexity** — Async coordination required
- **Eventual consistency** — Results not immediately available
- **State management** — Must handle partial failures

### Mitigation

- Atomic job state transitions
- Idempotent job handlers where possible
- Timeout monitoring for stuck jobs
- Dead letter handling for repeated failures

## Configuration

```yaml
jobs:
  max_concurrent_per_project: 3
  poll_interval_seconds: 1
  timeout_seconds: 3600  # 1 hour max
  retention_days: 90
  
  workers:
    count: 4
    types:
      - PARSE
      - PROFILE
      - GENERATE_MAPPINGS
      - STANDARDIZE
      - RECONCILE
      - REPORT
```

## References

- ANSWERING_OPEN_QUESTION.md (OQ-10: Job processing approach)
- API_SPECIFICATION.md (Job endpoints)
- NFR-PER-03 (Job timeout requirements)
