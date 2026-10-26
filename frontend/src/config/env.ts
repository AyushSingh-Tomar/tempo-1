/**
 * Runtime configuration, sourced exclusively from Vite env vars (see .env.example).
 * Nothing environment-specific is hard-coded here.
 */
export const API_BASE_URL: string = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/+$/, '');

export const DEFAULT_DEV_AUTH_TOKEN: string = import.meta.env.VITE_DEV_AUTH_TOKEN ?? '';

const parsedMax = Number(import.meta.env.VITE_MAX_UPLOAD_BYTES);
/** Client-side pre-check only. The server's configured limit is authoritative. */
export const MAX_UPLOAD_BYTES: number = Number.isFinite(parsedMax) && parsedMax > 0 ? parsedMax : 100 * 1024 * 1024;

export const ACCEPTED_UPLOAD_EXTENSIONS = ['.xlsx', '.csv'] as const;
