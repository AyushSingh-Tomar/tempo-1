/**
 * Client-side convenience list of runs started from this browser, so a user can
 * resume a run even if the backend has no "list runs for project" endpoint yet.
 * This is NOT a source of truth for run state: every run's status is always
 * re-fetched from GET /processing-runs/{id}.
 */
export interface RecentRunEntry {
  runId: string;
  projectId: string;
  filename?: string;
  createdAt: string;
}

const STORAGE_KEY = 'bordereaux.recentRuns';
const MAX_ENTRIES = 50;

function readAll(): RecentRunEntry[] {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? (parsed as RecentRunEntry[]) : [];
  } catch {
    return [];
  }
}

export function rememberRun(entry: RecentRunEntry): void {
  const rest = readAll().filter((e) => e.runId !== entry.runId);
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify([entry, ...rest].slice(0, MAX_ENTRIES)));
  } catch {
    /* storage unavailable - non-critical */
  }
}

export function recentRunsForProject(projectId: string): RecentRunEntry[] {
  return readAll().filter((e) => e.projectId === projectId);
}
