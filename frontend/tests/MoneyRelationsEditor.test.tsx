import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MoneyRelationsEditor } from '../src/components/relations/MoneyRelationsEditor';
import { api } from '../src/api/endpoints';
import { missingTreatyFigures, relationText, labelResolver } from '../src/utils/relations';
import type { AiStatus, ProcessingRun, RelationWorkspace } from '../src/api/types';

afterEach(() => {
  vi.restoreAllMocks();
});

const fields: RelationWorkspace['fields'] = [
  { field: 'gross_premium', label: 'Gross Premium', kind: 'dictionary', source_column: 'GWP', money_role: 'GROSS', filled_rows: 8, min: '1000', max: '8000', sample: ['1000'] },
  { field: 'commission', label: 'Commission', kind: 'dictionary', source_column: 'Comm', money_role: 'COMMISSION', filled_rows: 8, min: '250', max: '2000', sample: ['250'] },
  { field: 'net_premium', label: 'Net Premium', kind: 'dictionary', source_column: 'Net', money_role: 'NET', filled_rows: 8, min: '750', max: '6000', sample: ['750'] },
  { field: 'extra_amount_x', label: 'Amount X', kind: 'extra', source_column: 'Amount X', money_role: null, filled_rows: 8, min: '250', max: '2000', sample: ['250'] },
];

const treaty: RelationWorkspace['treaty_factors'] = [
  { name: 'commission_pct', value: '0.25' },
  { name: 'brokerage_pct', value: null },
  { name: 'tax_pct', value: '0.08' },
  { name: 'cession_pct', value: '0.5' },
  { name: 'order_pct', value: null },
  { name: 'fx_rate', value: null },
];

function workspace(over: Partial<RelationWorkspace> = {}): RelationWorkspace {
  return { editable: true, relations: [], fields, treaty_factors: treaty, tolerance: '0.005', ...over };
}

const run = { id: 'run-1', status: 'TREATY_FIGURES_VALIDATED' } as ProcessingRun;
const aiOn: AiStatus = { available: true, enabled: true, provider: 'dial', model: 'gpt-5-mini', timeout_seconds: 60, reason: null };

function mount(ws: RelationWorkspace, ai: AiStatus = aiOn) {
  vi.spyOn(api.moneyRelations, 'workspace').mockResolvedValue(ws);
  vi.spyOn(api.ai, 'status').mockResolvedValue(ai);
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MoneyRelationsEditor run={run} />
    </QueryClientProvider>,
  );
}

describe('relation text helpers', () => {
  const labelOf = labelResolver(fields);
  it('renders readable labels, signs and treaty factors', () => {
    expect(
      relationText('net_premium', [{ field: 'gross_premium', sign: 1, factors: [] }, { field: 'commission', sign: -1, factors: [] }], labelOf, treaty),
    ).toBe('Net Premium = Gross Premium − Commission');
    expect(relationText('commission', [{ field: 'gross_premium', sign: 1, factors: ['commission_pct'] }], labelOf, treaty)).toBe(
      'Commission = Gross Premium × commission % (0.25)',
    );
  });
  it('flags treaty figures that were never entered (but not the per-currency fx rate)', () => {
    const terms = [{ field: 'gross_premium', sign: 1 as const, factors: ['brokerage_pct', 'fx_rate', 'tax_pct'] }];
    expect(missingTreatyFigures(terms, treaty)).toEqual(['brokerage_pct']);
  });
});

describe('MoneyRelationsEditor', () => {
  it('lets the user run the checks with nothing declared (built-in rules) and says so', async () => {
    mount(workspace());
    expect(await screen.findByText(/No relations declared: the built-in standard checks will run/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /run financial checks/i })).toBeEnabled();
  });

  it('shows declared relations with origin, AI tag and a missing-treaty warning', async () => {
    mount(
      workspace({
        relations: [
          { id: 'a', label: 'x', target_field: 'net_premium', terms: [{ field: 'gross_premium', sign: 1, factors: [] }, { field: 'commission', sign: -1, factors: [] }], expression: 'e', origin: 'USER', rationale: null, last_rows_evaluated: null, last_rows_failed: null, last_skipped_reason: null },
          { id: 'b', label: 'y', target_field: 'extra_amount_x', terms: [{ field: 'gross_premium', sign: 1, factors: ['brokerage_pct'] }], expression: 'e', origin: 'AI_SUGGESTED', rationale: 'looks like brokerage', last_rows_evaluated: null, last_rows_failed: null, last_skipped_reason: null },
        ],
      }),
    );
    expect(await screen.findByText('Net Premium = Gross Premium − Commission')).toBeInTheDocument();
    expect(screen.getByText('Amount X = Gross Premium × brokerage %')).toBeInTheDocument();
    expect(screen.getByText('Declared by you')).toBeInTheDocument();
    expect(screen.getByTitle('Suggested by AI, accepted by you')).toBeInTheDocument();
    expect(screen.getByText(/Needs brokerage_pct, which was not entered/)).toBeInTheDocument();
    expect(screen.getByText(/2 relation\(s\) will be checked/)).toBeInTheDocument();
  });

  it('builds a relation by hand and saves it as a USER relation', async () => {
    mount(workspace());
    const create = vi.spyOn(api.moneyRelations, 'create').mockResolvedValue({} as never);
    fireEvent.click(await screen.findByRole('button', { name: /declare a relation/i }));

    fireEvent.change(screen.getByLabelText('This column'), { target: { value: 'net_premium' } });
    fireEvent.change(screen.getByLabelText('Column', { selector: '#rel-field-0' }), { target: { value: 'gross_premium' } });
    fireEvent.click(screen.getByRole('button', { name: /add another column/i }));
    fireEvent.change(screen.getByLabelText('Column', { selector: '#rel-field-1' }), { target: { value: 'commission' } });

    expect(screen.getByLabelText('Relation preview')).toHaveTextContent('Net Premium = Gross Premium − Commission');
    fireEvent.click(screen.getByRole('button', { name: /save relation/i }));

    await waitFor(() => expect(create).toHaveBeenCalledOnce());
    expect(create.mock.calls[0][1]).toMatchObject({
      target_field: 'net_premium',
      origin: 'USER',
      terms: [
        { field: 'gross_premium', sign: 1, factors: [] },
        { field: 'commission', sign: -1, factors: [] },
      ],
    });
  });

  it('refuses a column defined by itself', async () => {
    mount(workspace());
    fireEvent.click(await screen.findByRole('button', { name: /declare a relation/i }));
    fireEvent.change(screen.getByLabelText('This column'), { target: { value: 'net_premium' } });
    fireEvent.change(screen.getByLabelText('Column', { selector: '#rel-field-0' }), { target: { value: 'net_premium' } });
    expect(screen.getByText(/cannot be defined by itself/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /save relation/i })).toBeDisabled();
  });

  it('shows AI suggestions with their measured agreement and adds one as AI_SUGGESTED', async () => {
    mount(workspace());
    vi.spyOn(api.moneyRelations, 'aiSuggest').mockResolvedValue({
      status: 'ok',
      message: 'AI proposed 1 relationship(s); each was re-checked against your data below.',
      interaction: { id: 'i', run_id: 'run-1', purpose: 'MONEY_RELATIONS', status: 'ok', message: 'AI proposed 1 relationship(s); each was re-checked against your data below.', model: 'gpt-5-mini', provider: 'dial', latency_ms: 8000, timeout_seconds: 60, items_sent: 4, items_resolved: 1, created_at: null },
      suggestions: [
        { label: 'Amount X is commission', target_field: 'extra_amount_x', terms: [{ field: 'gross_premium', sign: 1, factors: ['commission_pct'] }], expression: 'e', rationale: '25% of gross on every row', confidence: 0.9, agreement: '1.0000', rows_evaluated: 8 },
      ],
    });
    const create = vi.spyOn(api.moneyRelations, 'create').mockResolvedValue({} as never);

    fireEvent.click(await screen.findByRole('button', { name: /get ai suggestions/i }));
    expect(await screen.findByText('Amount X = Gross Premium × commission % (0.25)')).toBeInTheDocument();
    expect(screen.getByText('Holds on 100% of 8 rows in your file')).toBeInTheDocument();
    expect(screen.getByText('AI used')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /add to my relations/i }));
    await waitFor(() => expect(create).toHaveBeenCalledOnce());
    expect(create.mock.calls[0][1]).toMatchObject({ origin: 'AI_SUGGESTED', target_field: 'extra_amount_x' });
    expect(await screen.findByRole('button', { name: 'Added' })).toBeDisabled();
  });

  it('reports a timed-out AI as a result and keeps every manual action available', async () => {
    mount(workspace());
    vi.spyOn(api.moneyRelations, 'aiSuggest').mockResolvedValue({
      status: 'timeout',
      message: 'The AI did not answer within 60s. Retry, or continue without AI.',
      interaction: { id: 'i', run_id: 'run-1', purpose: 'MONEY_RELATIONS', status: 'timeout', message: 'The AI did not answer within 60s. Retry, or continue without AI.', model: 'gpt-5-mini', provider: 'dial', latency_ms: 60000, timeout_seconds: 60, items_sent: 4, items_resolved: 0, created_at: null },
      suggestions: [],
    });
    fireEvent.click(await screen.findByRole('button', { name: /get ai suggestions/i }));
    expect(await screen.findByText('AI timed out')).toBeInTheDocument();
    expect(screen.getByText(/did not answer within 60s/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /try ai again/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /declare a relation/i })).toBeEnabled();
    expect(screen.getByRole('button', { name: /add standard relations/i })).toBeEnabled();
    expect(screen.getByRole('button', { name: /run financial checks/i })).toBeEnabled();
  });

  it('disables only the AI button, with the reason, when AI is not configured', async () => {
    mount(workspace(), { ...aiOn, available: false, reason: 'AI is switched off (LLM_ENABLED=false).' });
    const btn = await screen.findByRole('button', { name: /get ai suggestions/i });
    expect(btn).toBeDisabled();
    expect(await screen.findByText(/AI suggestions are unavailable \(AI is switched off/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /declare a relation/i })).toBeEnabled();
    expect(screen.getByRole('button', { name: /run financial checks/i })).toBeEnabled();
  });
});
