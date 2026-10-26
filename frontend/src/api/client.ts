import { API_BASE_URL } from '../config/env';
import { getAuthToken } from '../stores/devAuth';
import { ApiError, errorFromBody } from './errors';

export interface Envelope<T> {
  data: T;
  meta: Record<string, unknown>;
}

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  body?: unknown;
  formData?: FormData;
  signal?: AbortSignal;
  /** Prefix the path with /api/v1 (default true). /health is unprefixed. */
  versioned?: boolean;
  /** Send the Authorization header (default true). */
  auth?: boolean;
}

export function apiUrl(path: string, versioned = true): string {
  return `${API_BASE_URL}${versioned ? '/api/v1' : ''}${path}`;
}

function authHeaders(): Record<string, string> {
  const token = getAuthToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function unwrap<T>(body: unknown): Envelope<T> {
  if (body && typeof body === 'object' && 'data' in (body as Record<string, unknown>)) {
    const b = body as { data: T; meta?: Record<string, unknown> };
    return { data: b.data, meta: b.meta ?? {} };
  }
  // Tolerate un-enveloped responses (e.g. /health).
  return { data: body as T, meta: {} };
}

export async function requestEnvelope<T>(path: string, opts: RequestOptions = {}): Promise<Envelope<T>> {
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (opts.auth !== false) Object.assign(headers, authHeaders());
  let body: BodyInit | undefined;
  if (opts.formData) {
    body = opts.formData;
  } else if (opts.body !== undefined) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(opts.body);
  }

  let res: Response;
  try {
    res = await fetch(apiUrl(path, opts.versioned !== false), {
      method: opts.method ?? 'GET',
      headers,
      body,
      signal: opts.signal,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') throw err;
    throw ApiError.network(err);
  }

  if (!res.ok) {
    let parsed: unknown = null;
    try {
      parsed = await res.json();
    } catch {
      /* non-JSON error body */
    }
    throw errorFromBody(res.status, parsed);
  }
  if (res.status === 204) return { data: undefined as T, meta: {} };

  let parsed: unknown;
  try {
    parsed = await res.json();
  } catch {
    throw new ApiError({
      status: res.status,
      code: 'INVALID_RESPONSE',
      message: 'The server returned a response that is not valid JSON.',
      kind: 'parse',
    });
  }
  return unwrap<T>(parsed);
}

export async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  return (await requestEnvelope<T>(path, opts)).data;
}

/**
 * Multipart upload with progress reporting (fetch has no upload progress).
 * `onProgress` receives 0-100.
 */
export function uploadWithProgress<T>(
  path: string,
  formData: FormData,
  onProgress?: (percent: number) => void,
  signal?: AbortSignal,
): Promise<Envelope<T>> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', apiUrl(path));
    xhr.setRequestHeader('Accept', 'application/json');
    for (const [k, v] of Object.entries(authHeaders())) xhr.setRequestHeader(k, v);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) onProgress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onerror = () => reject(ApiError.network(new Error('Upload failed: network error')));
    xhr.onabort = () => reject(new DOMException('Upload cancelled', 'AbortError'));
    xhr.onload = () => {
      let parsed: unknown = null;
      try {
        parsed = xhr.responseText ? JSON.parse(xhr.responseText) : null;
      } catch {
        /* non-JSON */
      }
      if (xhr.status >= 200 && xhr.status < 300) resolve(unwrap<T>(parsed));
      else reject(errorFromBody(xhr.status, parsed));
    };
    signal?.addEventListener('abort', () => xhr.abort());
    xhr.send(formData);
  });
}

function filenameFromDisposition(header: string | null): string | null {
  if (!header) return null;
  const star = /filename\*=(?:UTF-8'')?([^;]+)/i.exec(header);
  if (star) return decodeURIComponent(star[1].trim().replace(/^"|"$/g, ''));
  const plain = /filename="?([^";]+)"?/i.exec(header);
  return plain ? plain[1].trim() : null;
}

/** Downloads an authenticated file response and hands it to the browser. */
export async function downloadFile(path: string, fallbackName: string): Promise<{ filename: string; size: number }> {
  let res: Response;
  try {
    res = await fetch(apiUrl(path), { headers: authHeaders() });
  } catch (err) {
    throw ApiError.network(err);
  }
  if (!res.ok) {
    let parsed: unknown = null;
    try {
      parsed = await res.json();
    } catch {
      /* binary or empty */
    }
    throw errorFromBody(res.status, parsed);
  }
  const blob = await res.blob();
  const filename = filenameFromDisposition(res.headers.get('Content-Disposition')) ?? fallbackName;
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  return { filename, size: blob.size };
}
