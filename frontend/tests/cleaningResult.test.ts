import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from '../src/api/endpoints';

afterEach(() => {
  vi.restoreAllMocks();
});

describe('api.cleaning.result', () => {
  it('unwraps the latest result from the backend envelope', async () => {
    const latest = {
      id: 'clean-1',
      run_id: 'run-1',
      attempt_number: 2,
      before_row_count: 120,
      before_column_count: 7,
      after_row_count: 119,
      after_column_count: 7,
      transformations: [{ description: 'Trim whitespace' }],
      warnings: [],
      status: 'PENDING_REVIEW',
      created_at: '2026-10-13T00:00:00Z',
    };

    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ data: { latest, history: [latest] } }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    );

    const result = await api.cleaning.result('run-1');

    expect(result).toMatchObject({
      id: 'clean-1',
      attempt_number: 2,
      before_row_count: 120,
      before_column_count: 7,
      after_row_count: 119,
      after_column_count: 7,
    });
  });
});
