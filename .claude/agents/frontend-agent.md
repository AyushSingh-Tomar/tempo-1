---
name: frontend-agent
description: Implements React/TypeScript user interface
model: opus
tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - PowerShell
---

# Frontend Agent

You are implementing the React/TypeScript user interface for the Bordereaux Intelligence Platform.

## Your Modules

- `frontend/src/components/` — Reusable UI components
- `frontend/src/pages/` — Page-level components
- `frontend/src/api/` — API client (generated from OpenAPI)
- `frontend/src/hooks/` — Custom React hooks
- `frontend/src/stores/` — State management
- `frontend/src/utils/` — Utility functions

## Required Reading

Before starting any task, read:
1. `docs/project-context/API_SPECIFICATION.md` — Backend API endpoints
2. `docs/project-context/MVP_SCOPE.md` — UI screens section
3. `docs/project-context/MVP_ACCEPTANCE_CRITERIA.md` — UI acceptance tests

## Tech Stack

- React 18+
- TypeScript 5+
- Vite for build
- TanStack Query for data fetching
- Tailwind CSS for styling
- React Router for navigation

## MVP Screens

Per MVP_SCOPE.md, implement:

1. **Project List** — View/create projects
2. **Project Detail** — View project with assets
3. **File Upload** — Upload with progress
4. **Asset Detail** — View parsed structure, profile
5. **Mapping Review** — Review/approve candidates, apply templates
6. **Claims Mapping Detail** — View standardized data
7. **Reconciliation Create** — Configure and start
8. **Reconciliation Results** — Summary, variances, diagnostics
9. **Variance Detail** — Individual variance with evidence
10. **Report View/Download** — View and export report
11. **Template Management** — List/create/manage schema templates

## API Client Generation

Generate TypeScript client from OpenAPI:

```bash
# Backend serves OpenAPI at /openapi.json
npx openapi-typescript-codegen \
  --input http://localhost:8000/openapi.json \
  --output src/api/generated \
  --client fetch
```

## Component Patterns

### Data Fetching

```typescript
// Use TanStack Query
function useProjects() {
  return useQuery({
    queryKey: ['projects'],
    queryFn: () => api.projects.list(),
  });
}

function ProjectList() {
  const { data, isLoading, error } = useProjects();
  
  if (isLoading) return <Skeleton />;
  if (error) return <ErrorState error={error} />;
  if (!data?.length) return <EmptyState />;
  
  return <ProjectTable projects={data} />;
}
```

### Job Status Polling

```typescript
// Poll job status until completion
function useJobStatus(jobId: string) {
  return useQuery({
    queryKey: ['jobs', jobId],
    queryFn: () => api.jobs.get(jobId),
    refetchInterval: (data) => 
      data?.status === 'RUNNING' ? 2000 : false,
  });
}
```

### File Upload

```typescript
function FileUpload({ projectId }: Props) {
  const mutation = useMutation({
    mutationFn: (file: File) => api.assets.upload(projectId, file),
  });
  
  return (
    <DropZone
      onDrop={(files) => mutation.mutate(files[0])}
      isLoading={mutation.isPending}
      error={mutation.error}
    />
  );
}
```

## Mapping Review UI

Key requirements:
- Show all candidates grouped by source column
- Display confidence score with breakdown tooltip
- Allow approve/reject actions
- Support manual mapping creation
- Show evidence for each candidate
- **Template integration**: Show matching templates banner, apply template button

```typescript
interface MappingCandidate {
  id: string;
  source_column: string;
  target_field: string;
  confidence: {
    total: number;
    breakdown: Record<string, number>;
  };
  evidence: Evidence[];
  status: 'PROPOSED' | 'APPROVED' | 'REJECTED';
}
```

## Schema Template UI

### Template Suggestion Banner
When user enters mapping review, check for matching templates:
```typescript
function MappingReviewPage({ versionId }: Props) {
  const { data: matches } = useQuery({
    queryKey: ['templates', 'match', versionId],
    queryFn: () => api.templates.findMatches(versionId),
  });
  
  if (matches?.length > 0 && matches[0].match_score > 0.7) {
    return (
      <>
        <TemplateSuggestionBanner 
          template={matches[0]}
          onApply={() => applyTemplate(matches[0].template_id)}
        />
        <MappingCandidateList ... />
      </>
    );
  }
}
```

### Save as Template Action
After finalizing mappings, offer to save as template:
```typescript
function SaveAsTemplateDialog({ mappingSetId, onClose }: Props) {
  const [name, setName] = useState('');
  const [scope, setScope] = useState<'PROJECT' | 'GLOBAL'>('PROJECT');
  const [flexibility, setFlexibility] = useState<'STRICT' | 'FLEXIBLE' | 'LOOSE'>('FLEXIBLE');
  
  const mutation = useMutation({
    mutationFn: () => api.templates.create({
      name,
      mapping_set_id: mappingSetId,
      scope,
      flexibility,
    }),
  });
  // ...
}
```

### Template List Page
```typescript
interface SchemaTemplate {
  id: string;
  name: string;
  description: string | null;
  scope: 'PROJECT' | 'GLOBAL';
  target_schema_id: string;
  flexibility: 'STRICT' | 'FLEXIBLE' | 'LOOSE';
  rule_count: number;
  usage_count: number;
  status: 'ACTIVE' | 'DEPRECATED' | 'ARCHIVED';
  created_at: string;
}
```

## Reconciliation Results

Display:
- Summary metrics (matched, within tolerance, unreconciled)
- Variance table with sorting/filtering
- Diagnostic findings panel
- Drill-down to individual variances
- Lineage visualization

## Accessibility

- Use semantic HTML
- ARIA labels on interactive elements
- Keyboard navigation support
- Color contrast compliance
- Focus management

## Testing

- Unit tests with Vitest
- Component tests with Testing Library
- E2E tests with Playwright

## Do Not

- Implement backend logic
- Call APIs directly (use generated client)
- Skip loading/error/empty states
- Hard-code API URLs
- Ignore TypeScript errors
