import { API_BASE_URL } from '../config/env';

export interface ApiErrorDetail {
  field?: string;
  code?: string;
  message?: string;
  [key: string]: unknown;
}

export type ApiErrorKind = 'network' | 'http' | 'parse';

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: ApiErrorDetail[];
  readonly requestId?: string;
  readonly kind: ApiErrorKind;

  constructor(opts: {
    status: number;
    code: string;
    message: string;
    details?: ApiErrorDetail[];
    requestId?: string;
    kind?: ApiErrorKind;
  }) {
    super(opts.message);
    this.name = 'ApiError';
    this.status = opts.status;
    this.code = opts.code;
    this.details = opts.details ?? [];
    this.requestId = opts.requestId;
    this.kind = opts.kind ?? 'http';
  }

  static network(cause: unknown): ApiError {
    return new ApiError({
      status: 0,
      code: 'NETWORK_ERROR',
      message: cause instanceof Error ? cause.message : 'Network request failed',
      kind: 'network',
    });
  }
}

export function isApiError(err: unknown): err is ApiError {
  return err instanceof ApiError;
}

function normalizeDetails(raw: unknown): ApiErrorDetail[] {
  if (Array.isArray(raw)) {
    return raw.map((d) => (d && typeof d === 'object' ? (d as ApiErrorDetail) : { message: String(d) }));
  }
  if (raw && typeof raw === 'object') return [raw as ApiErrorDetail];
  if (typeof raw === 'string') return [{ message: raw }];
  return [];
}

/** Builds an ApiError from a parsed (or unparseable) error response body. */
export function errorFromBody(status: number, body: unknown): ApiError {
  const b = body as
    | { error?: { code?: string; message?: string; details?: unknown }; meta?: { request_id?: string }; detail?: unknown }
    | null
    | undefined;
  if (b && typeof b === 'object' && b.error && typeof b.error === 'object') {
    return new ApiError({
      status,
      code: b.error.code ?? `HTTP_${status}`,
      message: b.error.message ?? `Request failed (HTTP ${status})`,
      details: normalizeDetails(b.error.details),
      requestId: b.meta?.request_id,
    });
  }
  // FastAPI default shape {"detail": ...} in case a route bypasses the envelope handler.
  if (b && typeof b === 'object' && 'detail' in b) {
    const detail = b.detail;
    return new ApiError({
      status,
      code: `HTTP_${status}`,
      message: typeof detail === 'string' ? detail : `Request failed (HTTP ${status})`,
      details: typeof detail === 'string' ? [] : normalizeDetails(detail),
    });
  }
  return new ApiError({ status, code: `HTTP_${status}`, message: `Request failed (HTTP ${status})` });
}

export const RUN_TRANSITION_CODES = new Set(['INVALID_RUN_TRANSITION', 'INVALID_STATE']);

export function isInvalidTransition(err: unknown): boolean {
  return isApiError(err) && err.status === 409 && RUN_TRANSITION_CODES.has(err.code);
}

/** Network failure or an endpoint the backend does not serve (yet). */
export function isNotAvailable(err: unknown): boolean {
  return isApiError(err) && (err.kind === 'network' || err.status === 404 || err.status === 405 || err.status === 501);
}

/** Plain-language, user-facing description of any error thrown by the API client. */
export function describeError(err: unknown): string {
  if (!isApiError(err)) {
    return err instanceof Error ? err.message : 'An unexpected error occurred.';
  }
  if (err.kind === 'network') {
    return `Cannot reach the server${API_BASE_URL ? ` at ${API_BASE_URL}` : ''}. Check that the backend is running, then try again.`;
  }
  if (err.kind === 'parse') return err.message;
  switch (err.status) {
    case 401:
      return 'You are not authenticated. Check the dev identity (VITE_DEV_AUTH_TOKEN or the header switcher).';
    case 403:
      return `Permission denied. ${err.message}`.trim();
    case 404:
      return err.message && !/^Request failed/.test(err.message)
        ? err.message
        : 'Not found. This resource (or endpoint) is not available on the server.';
    case 409:
      if (RUN_TRANSITION_CODES.has(err.code)) {
        return `This action is not allowed at the run's current stage (${err.message}). The run has been refreshed to show its actual status.`;
      }
      return err.message;
    case 413:
      return 'The file is larger than the server allows.';
    default:
      return err.message;
  }
}

/** Field-level messages from a validation error, keyed by field name. */
export function fieldErrors(err: unknown): Record<string, string> {
  const out: Record<string, string> = {};
  if (!isApiError(err)) return out;
  for (const d of err.details) {
    const field = typeof d.field === 'string' ? d.field : typeof d.loc === 'string' ? d.loc : undefined;
    if (field && d.message) out[field] = out[field] ? `${out[field]}; ${d.message}` : d.message;
  }
  return out;
}
