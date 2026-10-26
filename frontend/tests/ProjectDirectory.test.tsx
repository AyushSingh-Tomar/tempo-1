import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ProjectDirectory } from '../src/components/projects/ProjectDirectory';
import { ProjectListPage } from '../src/pages/ProjectListPage';
import { api } from '../src/api/endpoints';
import { ApiError } from '../src/api/errors';
import { setAuthToken } from '../src/stores/devAuth';
import type { Project } from '../src/api/types';

const projects: Project[] = [
  { id: 'p1', name: 'Q3 2026 Bordereaux', description: 'Marine', created_at: '2026-07-01T00:00:00Z' },
  { id: 'p2', name: 'Casualty renewals', description: null },
];

function renderWith(node: React.ReactNode) {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter>{node}</MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  window.localStorage.clear();
  vi.spyOn(api.projects, 'list').mockResolvedValue(projects);
  vi.spyOn(api.formats, 'list').mockResolvedValue([]);
});

afterEach(() => {
  vi.restoreAllMocks();
  setAuthToken('');
  window.localStorage.clear();
});

describe('ProjectDirectory', () => {
  it('lists the projects and filters them by name or description', async () => {
    setAuthToken('dev-analyst1-analyst');
    renderWith(<ProjectDirectory />);
    expect(await screen.findByText('Q3 2026 Bordereaux')).toBeInTheDocument();
    expect(screen.getByText('Casualty renewals')).toBeInTheDocument();
    expect(screen.getByText('2 of 2')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Search projects'), { target: { value: 'marine' } });
    expect(screen.queryByText('Casualty renewals')).not.toBeInTheDocument();
    expect(screen.getByText('1 of 2')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Search projects'), { target: { value: 'zzz' } });
    expect(screen.getByText(/No project matches/)).toBeInTheDocument();
  });

  it.each(['admin', 'analyst', 'reviewer', 'viewer'])('offers no delete to the %s role', async (role) => {
    setAuthToken(`dev-u1-${role}`);
    renderWith(<ProjectDirectory />);
    await screen.findByText('Q3 2026 Bordereaux');
    expect(screen.queryByRole('button', { name: /Delete project/ })).not.toBeInTheDocument();
    expect(screen.getByText('Only a project owner can delete a project.')).toBeInTheDocument();
  });

  it('lets a project owner delete only after typing the exact project name', async () => {
    setAuthToken('dev-owner1-project_owner');
    const remove = vi.spyOn(api.projects, 'remove').mockResolvedValue({ id: 'p1', deleted: true });
    renderWith(<ProjectDirectory />);
    fireEvent.click(await screen.findByRole('button', { name: 'Delete project Q3 2026 Bordereaux' }));

    const dialog = screen.getByRole('dialog');
    const confirm = within(dialog).getByRole('button', { name: 'Delete project' });
    expect(confirm).toBeDisabled();
    const input = within(dialog).getByLabelText(/Type/);
    for (const wrong of ['', 'q3 2026 bordereaux', 'Q3 2026', 'Q3 2026 Bordereaux!']) {
      fireEvent.change(input, { target: { value: wrong } });
      expect(confirm).toBeDisabled();
    }
    fireEvent.change(input, { target: { value: '  Q3 2026 Bordereaux ' } });
    expect(confirm).toBeEnabled();
    fireEvent.click(confirm);

    await waitFor(() => expect(remove).toHaveBeenCalledWith('p1', 'Q3 2026 Bordereaux'));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  });

  it('can be cancelled, and cancelling deletes nothing', async () => {
    setAuthToken('dev-owner1-project_owner');
    const remove = vi.spyOn(api.projects, 'remove').mockResolvedValue({ id: 'p1', deleted: true });
    renderWith(<ProjectDirectory />);
    fireEvent.click(await screen.findByRole('button', { name: 'Delete project Casualty renewals' }));
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Cancel' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Delete project Casualty renewals' }));
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(remove).not.toHaveBeenCalled();
  });

  it('hides the project from the directory immediately after archiving', async () => {
    setAuthToken('dev-owner1-project_owner');
    renderWith(<ProjectDirectory />);
    expect(await screen.findByText('Q3 2026 Bordereaux')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Project actions for Q3 2026 Bordereaux' }));
    fireEvent.click(screen.getByRole('button', { name: 'Archive project' }));

    await waitFor(() => expect(screen.queryByText('Q3 2026 Bordereaux')).not.toBeInTheDocument());
  });

  it("shows the server's refusal and keeps the dialog open", async () => {
    setAuthToken('dev-owner1-project_owner');
    vi.spyOn(api.projects, 'remove').mockRejectedValue(
      new ApiError({ status: 403, code: 'AUTHORIZATION_ERROR', message: 'Only a project owner can delete a project', kind: 'http' }),
    );
    renderWith(<ProjectDirectory />);
    fireEvent.click(await screen.findByRole('button', { name: 'Delete project Q3 2026 Bordereaux' }));
    fireEvent.change(screen.getByLabelText(/Type/), { target: { value: 'Q3 2026 Bordereaux' } });
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Delete project' }));
    expect(await within(screen.getByRole('dialog')).findByRole('alert')).toHaveTextContent('Only a project owner');
  });

  it('still creates projects exactly as before', async () => {
    setAuthToken('dev-analyst1-analyst');
    const create = vi.spyOn(api.projects, 'create').mockResolvedValue({ id: 'p3', name: 'New one' });
    renderWith(<ProjectDirectory />);
    await screen.findByText('Q3 2026 Bordereaux');
    fireEvent.click(screen.getByRole('button', { name: 'New project' }));
    fireEvent.change(screen.getByLabelText(/Name/), { target: { value: '  New one ' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create project' }));
    await waitFor(() => expect(create).toHaveBeenCalledWith({ name: 'New one', description: undefined }));
  });
});

describe('ProjectListPage', () => {
  it('shows both directories', async () => {
    setAuthToken('dev-analyst1-analyst');
    renderWith(<ProjectListPage />);
    expect(screen.getByRole('heading', { name: 'Projects' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Final formats' })).toBeInTheDocument();
    expect(await screen.findByText('Q3 2026 Bordereaux')).toBeInTheDocument();
    expect(await screen.findByText('No saved formats yet')).toBeInTheDocument();
  });
});
