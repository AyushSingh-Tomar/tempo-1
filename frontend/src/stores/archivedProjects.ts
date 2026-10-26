import type { Project } from '../api/types';

const STORAGE_KEY = 'bordereaux.archived-projects.v1';
const CHANGE_EVENT = 'bordereaux.archived-projects.change';

export interface ArchivedProjectRecord {
  id: string;
  name: string;
  description?: string | null;
  created_at?: string;
  updated_at?: string;
  archived_at: string;
}

function readRaw(): ArchivedProjectRecord[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as ArchivedProjectRecord[]) : [];
  } catch {
    return [];
  }
}

function writeRaw(items: ArchivedProjectRecord[]) {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
  window.dispatchEvent(new Event(CHANGE_EVENT));
}

export function getArchivedProjects(): Project[] {
  return readRaw().map(({ id, name, description, created_at, updated_at }) => ({
    id,
    name,
    description,
    created_at,
    updated_at,
  }));
}

export function isArchivedProject(id: string): boolean {
  return readRaw().some((item) => item.id === id);
}

export function listenForArchivedProjectChanges(listener: () => void) {
  if (typeof window === 'undefined') return () => undefined;
  window.addEventListener(CHANGE_EVENT, listener);
  return () => window.removeEventListener(CHANGE_EVENT, listener);
}

export function archiveProject(project: Project): Project[] {
  const items = readRaw();
  if (items.some((entry) => entry.id === project.id)) return getArchivedProjects();

  const next = [
    {
      id: project.id,
      name: project.name,
      description: project.description ?? null,
      created_at: project.created_at,
      updated_at: project.updated_at ?? project.created_at,
      archived_at: new Date().toISOString(),
    },
    ...items,
  ];
  writeRaw(next);
  return getArchivedProjects();
}

export function restoreArchivedProject(projectId: string): Project[] {
  const next = readRaw().filter((entry) => entry.id !== projectId);
  writeRaw(next);
  return getArchivedProjects();
}

export function deleteArchivedProject(projectId: string): Project[] {
  const next = readRaw().filter((entry) => entry.id !== projectId);
  writeRaw(next);
  return getArchivedProjects();
}
