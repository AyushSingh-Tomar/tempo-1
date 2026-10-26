import { useSyncExternalStore } from 'react';
import { DEFAULT_DEV_AUTH_TOKEN } from '../config/env';

/**
 * Dev-only identity store. The backend's DevAuthProvider accepts
 * `Authorization: Bearer dev-{user_id}-{role}`. The default comes from
 * VITE_DEV_AUTH_TOKEN; the header's "Dev identity" switcher can override it
 * (persisted in localStorage) so reviewer-only actions can be exercised locally.
 */
export const DEV_ROLES = ['admin', 'project_owner', 'analyst', 'reviewer', 'viewer'] as const;
export type DevRole = (typeof DEV_ROLES)[number];

const STORAGE_KEY = 'bordereaux.devAuthToken';
const listeners = new Set<() => void>();

export function getAuthToken(): string {
  try {
    return window.localStorage.getItem(STORAGE_KEY) || DEFAULT_DEV_AUTH_TOKEN;
  } catch {
    return DEFAULT_DEV_AUTH_TOKEN;
  }
}

export function setAuthToken(token: string): void {
  try {
    if (token) window.localStorage.setItem(STORAGE_KEY, token);
    else window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* storage unavailable - token falls back to env default */
  }
  listeners.forEach((l) => l());
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useAuthToken(): string {
  return useSyncExternalStore(subscribe, getAuthToken, getAuthToken);
}

export function buildDevToken(userId: string, role: DevRole): string {
  return `dev-${userId}-${role}`;
}

/** The role of the current identity (null when the token isn't a recognised dev token). */
export function useDevRole(): DevRole | null {
  return parseDevToken(useAuthToken())?.role ?? null;
}

/** Parses `dev-{user_id}-{role}`; role may itself contain an underscore (project_owner). */
export function parseDevToken(token: string): { userId: string; role: DevRole } | null {
  const match = /^dev-(.+)-([a-z_]+)$/.exec(token);
  if (!match) return null;
  const role = match[2] as DevRole;
  if (!DEV_ROLES.includes(role)) return null;
  return { userId: match[1], role };
}
