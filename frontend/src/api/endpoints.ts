/**
 * Typed wrappers for every iteration-1 endpoint. Components and hooks must go
 * through this module (never fetch directly). Response-shape normalization for
 * fields the contract leaves open lives here, not in components.
 */
import { downloadFile, request, requestEnvelope, uploadWithProgress } from './client';
import type {
  AiActivity,
  AiKeySaveResult,
  AiKeyTest,
  AiInteraction,
  AiStatus,
  MoneyRelation,
  RelationDraft,
  RelationResult,
  RelationSuggestResult,
  RelationWorkspace,
  ArtifactType,
  ApprovedMapping,
  CandidateListResult,
  CleaningResult,
  CleaningWarning,
  ColumnRoleSuggestion,
  DerivedTreatyInputs,
  DiscrepancyFinding,
  DiscrepancyListResult,
  DiscrepancyOverride,
  HealthStatus,
  Job,
  MappingCandidate,
  Me,
  ProcessingRun,
  Project,
  PeriodExtract,
  FormatTemplate,
  FormatTemplateColumn,
  Report,
  TargetFormat,
  Transformation,
  TreatyFigures,
  TreatyFiguresRequest,
} from './types';
import type {
  ColumnValues,
  DatasetKind,
  DatasetPreview,
  EncodingInfo,
  EncodingOptions,
  FilePatch as ReconFilePatch,
  FinalizeRequest as ReconFinalizeRequest,
  GroupRecords,
  ReconDataset,
  ReconFile,
  ReconRun,
  ReconRunRequest,
  SchemaPreview,
} from './reconTypes';

const enc = encodeURIComponent;

function asStringArray(v: unknown): string[] | null {
  return Array.isArray(v) && v.every((x) => typeof x === 'string') ? (v as string[]) : null;
}

function asNumber(v: unknown): number | null {
  return typeof v === 'number' && Number.isFinite(v) ? v : null;
}

function pickArray<T>(data: unknown, keys: string[]): T[] {
  if (Array.isArray(data)) return data as T[];
  if (data && typeof data === 'object') {
    for (const k of keys) {
      const v = (data as Record<string, unknown>)[k];
      if (Array.isArray(v)) return v as T[];
    }
  }
  return [];
}

function pickField(data: unknown, meta: Record<string, unknown>, key: string): unknown {
  if (data && typeof data === 'object' && !Array.isArray(data) && key in (data as object)) {
    return (data as Record<string, unknown>)[key];
  }
  return meta[key];
}

function normalizeConfidenceValue(value: unknown): number {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string') {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }
  return 0;
}

function normalizeMappingCandidate(data: unknown): MappingCandidate | null {
  if (!data || typeof data !== 'object') return null;

  const candidate = data as Record<string, unknown>;
  const total = normalizeConfidenceValue(candidate.confidence_total ?? candidate.total ?? 0);
  const breakdown = candidate.confidence_breakdown;

  return {
    id: typeof candidate.id === 'string' ? candidate.id : '',
    source_column: typeof candidate.source_column === 'string' ? candidate.source_column : '',
    target_field: typeof candidate.target_field === 'string' ? candidate.target_field : null,
    confidence: {
      total,
      breakdown:
        breakdown && typeof breakdown === 'object' && !Array.isArray(breakdown)
          ? Object.fromEntries(
              Object.entries(breakdown as Record<string, unknown>).map(([k, v]) => [k, normalizeConfidenceValue(v)]),
            )
          : {},
    },
    evidence: Array.isArray(candidate.evidence) ? (candidate.evidence as unknown as MappingCandidate['evidence']) : [],
    status: typeof candidate.status === 'string' ? (candidate.status as MappingCandidate['status']) : 'PROPOSED',
    auto_approve_eligible:
      typeof candidate.auto_approve_eligible === 'boolean' ? candidate.auto_approve_eligible : undefined,
    sample_values: Array.isArray(candidate.sample_values) ? candidate.sample_values : undefined,
    rejection_reason:
      typeof candidate.rejection_reason === 'string' || candidate.rejection_reason === null
        ? candidate.rejection_reason
        : undefined,
  };
}

/** True if a response object looks like a Job (async action) rather than a domain object. */
export function isJobLike(v: unknown): v is Job {
  if (!v || typeof v !== 'object') return false;
  const o = v as Record<string, unknown>;
  return (
    typeof o.id === 'string' &&
    typeof o.type === 'string' &&
    typeof o.status === 'string' &&
    ['PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED'].includes(o.status as string) &&
    'progress' in o
  );
}

/** Extracts a job id from an action response: either the job itself or a `job_id` field. */
export function jobIdFrom(v: unknown): string | null {
  if (isJobLike(v)) return v.id;
  if (v && typeof v === 'object') {
    const jid = (v as Record<string, unknown>).job_id;
    if (typeof jid === 'string') return jid;
  }
  return null;
}

export type UploadResult =
  | { kind: 'run'; run: ProcessingRun }
  | { kind: 'sheet_selection'; sheets: string[] };

/** Interprets the upload response: a created run, or a request to choose a worksheet. */
export function interpretUploadResponse(data: unknown, meta: Record<string, unknown>): UploadResult {
  const sheets =
    asStringArray(pickField(data, meta, 'sheets')) ??
    asStringArray(pickField(data, meta, 'sheet_names')) ??
    asStringArray(pickField(data, meta, 'available_sheets'));
  const hasRunId = !!data && typeof data === 'object' && typeof (data as { id?: unknown }).id === 'string';
  if (!hasRunId && sheets && sheets.length > 0) return { kind: 'sheet_selection', sheets };
  if (hasRunId) {
    const maybeRun = (data as { run?: ProcessingRun }).run;
    return { kind: 'run', run: maybeRun && typeof maybeRun === 'object' ? maybeRun : (data as ProcessingRun) };
  }
  if (data && typeof data === 'object' && (data as { run?: unknown }).run) {
    return { kind: 'run', run: (data as { run: ProcessingRun }).run };
  }
  throw new Error('Unexpected upload response: neither a processing run nor a worksheet list was returned.');
}

/** Some servers signal sheet selection as an error with the sheet list in details. */
export function sheetsFromUploadError(details: Array<Record<string, unknown>>): string[] | null {
  for (const d of details) {
    const s = asStringArray(d.sheets) ?? asStringArray(d.sheet_names) ?? asStringArray(d.available_sheets);
    if (s && s.length) return s;
  }
  return null;
}

function normalizeCleaningResult(data: unknown): CleaningResult | null {
  if (!data || typeof data !== 'object') return null;

  const candidate = ((data as { latest?: unknown }).latest ?? data) as Record<string, unknown>;
  if (!candidate || typeof candidate !== 'object') return null;

  const toNumber = (key: string, fallback = 0): number => {
    const value = candidate[key];
    return typeof value === 'number' && Number.isFinite(value) ? value : fallback;
  };

  const transformations = Array.isArray(candidate.transformations) ? (candidate.transformations as Transformation[]) : [];
  const warnings = Array.isArray(candidate.warnings) ? (candidate.warnings as CleaningWarning[]) : [];

  return {
    id: typeof candidate.id === 'string' ? candidate.id : undefined,
    attempt_number: typeof candidate.attempt_number === 'number' ? candidate.attempt_number : 0,
    before_row_count: toNumber('before_row_count'),
    before_column_count: toNumber('before_column_count'),
    after_row_count: toNumber('after_row_count'),
    after_column_count: toNumber('after_column_count'),
    transformations,
    warnings,
    status: typeof candidate.status === 'string' ? candidate.status : 'PENDING_REVIEW',
    created_at: typeof candidate.created_at === 'string' ? candidate.created_at : undefined,
  };
}

export const api = {
  health: () => request<HealthStatus>('/health', { versioned: false, auth: false }),
  me: () => request<Me>('/me'),

  /** The platform-wide directory of saved final formats. */
  formats: {
    list: async (): Promise<FormatTemplate[]> =>
      pickArray<FormatTemplate>(await request<unknown>('/format-templates'), ['items', 'templates']),
    create: (body: { name: string; columns: FormatTemplateColumn[] }) =>
      request<FormatTemplate>('/format-templates', { method: 'POST', body }),
    update: (id: string, body: { name: string; columns: FormatTemplateColumn[] }) =>
      request<FormatTemplate>(`/format-templates/${enc(id)}`, { method: 'PUT', body }),
    remove: (id: string) => request<{ id: string; deleted: boolean }>(`/format-templates/${enc(id)}`, { method: 'DELETE' }),
    /** Reads a CSV/Excel (headers = columns, cells below = recognised terms). Saves nothing. */
    parseFile: async (file: File) => {
      const form = new FormData();
      form.append('file', file);
      return request<{ columns: string[]; terms: Record<string, string[]>; skipped_terms: number }>(
        '/format-templates/parse',
        { method: 'POST', formData: form },
      );
    },
  },

  projects: {
    list: async (): Promise<Project[]> => pickArray<Project>(await request<unknown>('/projects'), ['items', 'projects']),
    get: (projectId: string) => request<Project>(`/projects/${enc(projectId)}`),
    create: (body: { name: string; description?: string }) =>
      request<Project>('/projects', { method: 'POST', body }),
    /** Project owners only; the server also requires the exact project name. Soft delete: data and audit trail are kept. */
    remove: (projectId: string, confirmName: string) =>
      request<{ id: string; deleted: boolean }>(`/projects/${enc(projectId)}`, {
        method: 'DELETE',
        body: { confirm_name: confirmName },
      }),
    /** Assumed endpoint (not in the iteration-1 contract); callers treat 404 as "not available". */
    listRuns: async (projectId: string): Promise<ProcessingRun[]> =>
      pickArray<ProcessingRun>(await request<unknown>(`/projects/${enc(projectId)}/processing-runs`), [
        'items',
        'runs',
        'processing_runs',
      ]),
  },

  runs: {
    upload: async (
      projectId: string,
      file: File,
      sheetName: string | undefined,
      onProgress?: (pct: number) => void,
      signal?: AbortSignal,
    ): Promise<UploadResult> => {
      const fd = new FormData();
      fd.append('file', file);
      if (sheetName) fd.append('sheet_name', sheetName);
      const env = await uploadWithProgress<unknown>(
        `/projects/${enc(projectId)}/processing-runs`,
        fd,
        onProgress,
        signal,
      );
      return interpretUploadResponse(env.data, env.meta);
    },
    get: (runId: string) => request<ProcessingRun>(`/processing-runs/${enc(runId)}`),
    validate: (runId: string) => request<unknown>(`/processing-runs/${enc(runId)}/validate`, { method: 'POST' }),
    clean: (runId: string) => request<unknown>(`/processing-runs/${enc(runId)}/clean`, { method: 'POST' }),
  },

  cleaning: {
    result: async (runId: string): Promise<CleaningResult> => {
      const env = await requestEnvelope<unknown>(`/processing-runs/${enc(runId)}/cleaning-result`);
      return normalizeCleaningResult(env.data) ?? {
        attempt_number: 0,
        before_row_count: 0,
        before_column_count: 0,
        after_row_count: 0,
        after_column_count: 0,
        transformations: [],
        warnings: [],
        status: 'PENDING_REVIEW',
      };
    },
    acknowledge: (runId: string) =>
      request<unknown>(`/processing-runs/${enc(runId)}/cleaning/acknowledge`, { method: 'POST' }),
    rerun: (runId: string, reason: string) =>
      request<unknown>(`/processing-runs/${enc(runId)}/cleaning/rerun`, { method: 'POST', body: { reason } }),
  },

  mappings: {
    /** `useAi: false` maps deterministically only. The reply carries the AI step's outcome in `ai`. */
    generate: (runId: string, opts: { useAi?: boolean } = {}) =>
      request<{ ai: AiInteraction | null }>(
        `/processing-runs/${enc(runId)}/mappings/generate${opts.useAi === false ? '?use_ai=false' : ''}`,
        { method: 'POST' },
      ),
    /** Runs the mapping AI step again on the current draft (e.g. after a timeout). Never throws for AI problems. */
    aiAssist: (runId: string) =>
      request<AiInteraction>(`/processing-runs/${enc(runId)}/mappings/ai-assist`, { method: 'POST' }),
    candidates: async (runId: string): Promise<CandidateListResult> => {
      const env = await requestEnvelope<unknown>(`/processing-runs/${enc(runId)}/mappings/candidates`);
      const rawCandidates = pickArray<unknown>(env.data, ['candidates', 'items']);
      const rawApprovedMappings = pickArray<unknown>(env.data, ['approved_mappings', 'approvedMappings']);
      return {
        candidates: rawCandidates.map((candidate) => normalizeMappingCandidate(candidate)).filter(Boolean) as MappingCandidate[],
        approvedMappings: rawApprovedMappings
          .map((mapping) => ({
            source_column: String((mapping as { source_column?: string }).source_column ?? ''),
            target_field: String((mapping as { target_field?: string }).target_field ?? ''),
          }))
          .filter((m) => !!m.source_column && !!m.target_field),
        requiredFields: asStringArray(pickField(env.data, env.meta, 'required_fields')),
        passthroughCount: asNumber(pickField(env.data, env.meta, 'passthrough_count')),
        targetFormat: (pickField(env.data, env.meta, 'target_format') as TargetFormat | null) ?? null,
      };
    },
    targetFormat: {
      get: (runId: string) => request<TargetFormat>(`/processing-runs/${enc(runId)}/mappings/target-format`),
      set: (
        runId: string,
        body: { mode: 'DEFAULT' | 'CUSTOM'; columns?: string[]; terms?: Record<string, string[]>; template_id?: string },
      ) =>
        request<TargetFormat>(`/processing-runs/${enc(runId)}/mappings/target-format`, { method: 'PUT', body }),
      /** Reads a CSV/Excel whose headers are the final columns and whose cells below are their recognised terms. Saves nothing. */
      parseTermsFile: async (
        runId: string,
        file: File,
      ): Promise<{ columns: string[]; terms: Record<string, string[]>; skipped_terms: number }> => {
        const form = new FormData();
        form.append('file', file);
        return request<{ columns: string[]; terms: Record<string, string[]>; skipped_terms: number }>(
          `/processing-runs/${enc(runId)}/mappings/target-format/parse-terms`,
          { method: 'POST', formData: form },
        );
      },
      parseFile: async (runId: string, file: File): Promise<string[]> => {
        const form = new FormData();
        form.append('file', file);
        const res = await request<{ columns: string[] }>(
          `/processing-runs/${enc(runId)}/mappings/target-format/parse`,
          { method: 'POST', formData: form },
        );
        return res.columns;
      },
    },
    approveExact: (runId: string) =>
      request<{ approved: number; skipped: { source_column: string; reason: string }[] }>(
        `/processing-runs/${enc(runId)}/mappings/approve-exact`,
        { method: 'POST' },
      ),
    reopen: async (candidateId: string) => {
      const env = await request<unknown>(`/mappings/${enc(candidateId)}/reopen`, { method: 'POST' });
      return normalizeMappingCandidate(env) ?? ({} as MappingCandidate);
    },
    approve: async (candidateId: string, comment?: string) => {
      const env = await request<unknown>(`/mappings/${enc(candidateId)}/approve`, {
        method: 'POST',
        body: comment ? { comment } : {},
      });
      return normalizeMappingCandidate(env) ?? ({} as MappingCandidate);
    },
    reject: async (candidateId: string, reason: string) => {
      const env = await request<unknown>(`/mappings/${enc(candidateId)}/reject`, { method: 'POST', body: { reason } });
      return normalizeMappingCandidate(env) ?? ({} as MappingCandidate);
    },
    manual: (runId: string, body: { source_column: string; target_field: string }) =>
      request<ApprovedMapping>(`/processing-runs/${enc(runId)}/mappings/manual`, { method: 'POST', body }),
    finalize: (runId: string) =>
      request<unknown>(`/processing-runs/${enc(runId)}/mappings/finalize`, { method: 'POST' }),
  },

  treaty: {
    derived: (runId: string) =>
      request<DerivedTreatyInputs>(`/processing-runs/${enc(runId)}/treaty-figures/derived`),
    submit: (runId: string, body: TreatyFiguresRequest) =>
      request<TreatyFigures>(`/processing-runs/${enc(runId)}/treaty-figures`, { method: 'POST', body }),
  },

  financialChecks: {
    run: (runId: string) =>
      request<{ relation_results?: RelationResult[]; discrepancies_found?: number }>(
        `/processing-runs/${enc(runId)}/financial-checks/run`,
        { method: 'POST' },
      ),
  },

  ai: {
    status: () => request<AiStatus>('/ai/status'),
    /** The user's own API key. The key is write-only: it is never sent back, only its last 4 characters. */
    myKey: {
      save: (apiKey: string, opts: { skipTest?: boolean } = {}) =>
        request<AiKeySaveResult>('/me/ai-key', { method: 'PUT', body: { api_key: apiKey, skip_test: !!opts.skipTest } }),
      test: () => request<AiStatus & { test: AiKeyTest }>('/me/ai-key/test', { method: 'POST' }),
      remove: () => request<AiStatus & { removed: boolean }>('/me/ai-key', { method: 'DELETE' }),
    },
    activity: (runId: string) => request<AiActivity>(`/processing-runs/${enc(runId)}/ai/activity`),
  },

  moneyRelations: {
    workspace: (runId: string) => request<RelationWorkspace>(`/processing-runs/${enc(runId)}/money-relations`),
    create: (runId: string, body: RelationDraft) =>
      request<MoneyRelation>(`/processing-runs/${enc(runId)}/money-relations`, { method: 'POST', body }),
    update: (runId: string, id: string, body: RelationDraft) =>
      request<MoneyRelation>(`/processing-runs/${enc(runId)}/money-relations/${enc(id)}`, { method: 'PUT', body }),
    remove: (runId: string, id: string) =>
      request<{ deleted: string }>(`/processing-runs/${enc(runId)}/money-relations/${enc(id)}`, { method: 'DELETE' }),
    /** Deterministic: adds the standard premium-flow identities that fit the mapped columns. */
    addStandard: (runId: string) =>
      request<{ added: number; skipped: { expression: string; reason: string }[]; relations: MoneyRelation[] }>(
        `/processing-runs/${enc(runId)}/money-relations/standard`,
        { method: 'POST' },
      ),
    /** Always resolves: an AI problem is reported in `status` / `message`, not thrown. */
    aiSuggest: (runId: string) =>
      request<RelationSuggestResult>(`/processing-runs/${enc(runId)}/money-relations/ai-suggest`, { method: 'POST' }),
  },

  discrepancies: {
    list: async (runId: string): Promise<DiscrepancyListResult> => {
      const env = await requestEnvelope<unknown>(`/processing-runs/${enc(runId)}/discrepancies`);
      const total = pickField(env.data, env.meta, 'total_records');
      return {
        findings: pickArray<DiscrepancyFinding>(env.data, ['discrepancies', 'findings', 'items']),
        columnRoleSuggestions: pickArray<ColumnRoleSuggestion>(env.data, ['column_role_suggestions']),
        relations: pickArray<MoneyRelation>(env.data, ['relations']),
        checksPerformed: asStringArray(pickField(env.data, env.meta, 'checks_performed')),
        totalRecords: typeof total === 'number' ? total : null,
      };
    },
    override: (discrepancyId: string, body: { reason: string; comment?: string }) =>
      request<DiscrepancyOverride>(`/discrepancies/${enc(discrepancyId)}/override`, { method: 'POST', body }),
    proceed: (runId: string) =>
      request<unknown>(`/processing-runs/${enc(runId)}/discrepancies/proceed`, { method: 'POST' }),
  },

  reports: {
    generate: (runId: string) =>
      request<Report>(`/processing-runs/${enc(runId)}/reports/generate`, { method: 'POST' }),
    download: (runId: string, artifactType: ArtifactType) =>
      downloadFile(
        `/processing-runs/${enc(runId)}/download/${enc(artifactType)}`,
        artifactType === 'processed_file'
          ? `processed_${runId}.csv`
          : artifactType === 'audit_report'
            ? `audit_report_${runId}.json`
            : `audit_report_${runId}.txt`,
      ),
    /** Cuts the processed file to a year or quarter and stores it as an immutable version. Month-only dates in the period are included. */
    createPeriodExtract: (runId: string, period: { year: number; quarter?: number; field: string }) =>
      request<PeriodExtract>(`/processing-runs/${enc(runId)}/reports/period-extracts`, {
        method: 'POST',
        body: { period_field: period.field, year: period.year, ...(period.quarter ? { quarter: period.quarter } : {}) },
      }),
    listPeriodExtracts: (runId: string) =>
      request<{ extracts: PeriodExtract[] }>(`/processing-runs/${enc(runId)}/reports/period-extracts`).then((d) => d.extracts),
    downloadPeriodExtract: (runId: string, extract: PeriodExtract) =>
      downloadFile(
        `/processing-runs/${enc(runId)}/reports/period-extracts/${enc(extract.id)}/download`,
        `processed_${runId}_${extract.period_label}_v${extract.version_number}.csv`,
      ),
  },

  jobs: {
    get: (jobId: string) => request<Job>(`/jobs/${enc(jobId)}`),
  },

  /** Reconciliation workspace (datasets built from many files, then rule-based reconciliation). */
  recon: {
    encodings: () => request<EncodingOptions>('/recon/encodings'),

    listDatasets: async (projectId: string, kind?: DatasetKind): Promise<ReconDataset[]> =>
      pickArray<ReconDataset>(
        await request<unknown>(`/projects/${enc(projectId)}/recon/datasets${kind ? `?kind=${enc(kind)}` : ''}`),
        ['datasets'],
      ),
    createDataset: (projectId: string, body: { kind: DatasetKind; name: string }) =>
      request<ReconDataset>(`/projects/${enc(projectId)}/recon/datasets`, { method: 'POST', body }),
    getDataset: (datasetId: string) => request<ReconDataset>(`/recon/datasets/${enc(datasetId)}`),
    /** Use a completed run's processed file as the (final) bordereaux for reconciliation. Idempotent per run. */
    bordereauxFromRun: (runId: string) =>
      request<ReconDataset & { created: boolean }>(`/processing-runs/${enc(runId)}/reconciliation/bordereaux`, { method: 'POST' }),

    uploadFiles: async (
      datasetId: string,
      files: File[],
      opts: { encoding?: string; candidateEncodings?: string[] } = {},
      onProgress?: (pct: number) => void,
    ): Promise<ReconFile[]> => {
      const fd = new FormData();
      for (const f of files) fd.append('files', f);
      if (opts.encoding) fd.append('encoding', opts.encoding);
      if (opts.candidateEncodings?.length) fd.append('candidate_encodings', opts.candidateEncodings.join(','));
      const env = await uploadWithProgress<unknown>(`/recon/datasets/${enc(datasetId)}/files`, fd, onProgress);
      return pickArray<ReconFile>(env.data, ['files']);
    },
    patchFile: (datasetId: string, fileId: string, body: ReconFilePatch) =>
      request<ReconFile>(`/recon/datasets/${enc(datasetId)}/files/${enc(fileId)}`, { method: 'PATCH', body }),
    checkEncoding: (datasetId: string, fileId: string, candidateEncodings?: string[]) =>
      request<EncodingInfo>(`/recon/datasets/${enc(datasetId)}/files/${enc(fileId)}/encoding-check`, {
        method: 'POST',
        body: candidateEncodings?.length ? { candidate_encodings: candidateEncodings } : {},
      }),
    deleteFile: (datasetId: string, fileId: string) =>
      request<{ deleted: boolean }>(`/recon/datasets/${enc(datasetId)}/files/${enc(fileId)}`, { method: 'DELETE' }),

    schemaSummary: (datasetId: string, columnAliases: Record<string, string>) =>
      request<SchemaPreview>(`/recon/datasets/${enc(datasetId)}/schema-summary`, {
        method: 'POST',
        body: { column_aliases: columnAliases },
      }),
    finalize: (datasetId: string, body: ReconFinalizeRequest) =>
      request<ReconDataset>(`/recon/datasets/${enc(datasetId)}/finalize`, { method: 'POST', body }),
    preview: (datasetId: string, limit = 25) =>
      request<DatasetPreview>(`/recon/datasets/${enc(datasetId)}/preview?limit=${limit}`),
    columnValues: (datasetId: string, column: string, q?: string, limit = 50) =>
      request<ColumnValues>(
        `/recon/datasets/${enc(datasetId)}/columns/${enc(column)}/values?limit=${limit}${q ? `&q=${enc(q)}` : ''}`,
      ),

    createRun: (projectId: string, body: ReconRunRequest) =>
      request<ReconRun>(`/projects/${enc(projectId)}/recon/runs`, { method: 'POST', body }),
    listRuns: async (projectId: string): Promise<ReconRun[]> =>
      pickArray<ReconRun>(await request<unknown>(`/projects/${enc(projectId)}/recon/runs`), ['runs']),
    getRun: (runId: string) => request<ReconRun>(`/recon/runs/${enc(runId)}`),
    records: (runId: string, ruleId: string, side: 'bordereaux' | 'subledger', key: string[]) => {
      const qs = [`rule_id=${enc(ruleId)}`, `side=${side}`, ...key.map((k) => `key=${enc(k)}`)].join('&');
      return request<GroupRecords>(`/recon/runs/${enc(runId)}/records?${qs}`);
    },
    exportCsv: (runId: string) => downloadFile(`/recon/runs/${enc(runId)}/export`, `reconciliation_${runId}.csv`),
  },
};

export type Api = typeof api;
