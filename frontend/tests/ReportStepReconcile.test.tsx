import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReportStep } from '../src/pages/steps/ReportStep';
import { api } from '../src/api/endpoints';
import type { ProcessingRun } from '../src/api/types';

function Where() {
  const loc = useLocation();
  return <div data-testid="where">{loc.pathname + loc.search}</div>;
}

const run = { id: 'run-1', project_id: 'proj-1', status: 'COMPLETED' } as unknown as ProcessingRun;

function renderStep() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={['/runs/run-1']}>
        <Routes>
          <Route path="/runs/:id" element={<ReportStep run={run} />} />
          <Route path="*" element={<Where />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('ReportStep -> reconciliation', () => {
  it('offers both routes and sends the processed file as the bordereaux', async () => {
    localStorage.setItem('bordereaux.devAuthToken', 'dev-admin1-admin');
    vi.spyOn(api.recon, 'bordereauxFromRun').mockResolvedValue({ id: 'ds-9', created: true } as never);
    renderStep();
    expect(screen.getByRole('link', { name: /your own bordereaux and subledger/i }).getAttribute('href')).toBe(
      '/projects/proj-1/reconciliation',
    );
    fireEvent.click(screen.getByRole('button', { name: /Reconcile this file with a subledger/i }));
    await waitFor(() =>
      expect(screen.getByTestId('where').textContent).toBe(
        '/projects/proj-1/reconciliation?bordereaux=ds-9&tab=subledger&run=run-1',
      ),
    );
  });
});
