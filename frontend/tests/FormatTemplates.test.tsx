import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { FormatTemplateEditor, splitTerms, validateFormat } from '../src/components/formats/FormatTemplateEditor';
import { FormatTemplateDirectory } from '../src/components/formats/FormatTemplateDirectory';
import { api } from '../src/api/endpoints';
import { setAuthToken } from '../src/stores/devAuth';
import type { FormatTemplate } from '../src/api/types';

const lloyds: FormatTemplate = {
  id: 'f1',
  name: "Lloyd's Standard",
  columns: [
    { name: 'UMR', terms: [] },
    { name: 'Premium Due', terms: ['GWP', 'Prime Brute'] },
  ],
  column_count: 2,
  term_count: 2,
  updated_at: '2026-10-01T00:00:00Z',
};
const acord: FormatTemplate = { id: 'f2', name: 'ACORD', columns: [{ name: 'Policy', terms: [] }], column_count: 1, term_count: 0 };

function renderWith(node: React.ReactNode) {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{node}</QueryClientProvider>,
  );
}

afterEach(() => {
  vi.restoreAllMocks();
  setAuthToken('');
});

describe('validateFormat / splitTerms', () => {
  it('keeps one distinct term per line', () => {
    expect(splitTerms(' GWP \n\ngwp\r\nPrime   Brute\n  ')).toEqual(['GWP', 'Prime Brute']);
  });

  it('accepts a well-formed format and trims it', () => {
    const { errors, columns } = validateFormat('  Mine ', [
      { name: ' Gross   Premium ', terms: 'GWP\nPrime Brute' },
      { name: '', terms: '' },
    ]);
    expect(errors).toEqual([]);
    expect(columns).toEqual([{ name: 'Gross Premium', terms: ['GWP', 'Prime Brute'] }]);
  });

  it.each([
    ['', [{ name: 'A', terms: '' }], 'Give the format a name.'],
    ['N', [{ name: '', terms: '' }], 'Add at least one column.'],
    ['N', [{ name: '', terms: 'orphan' }], 'Every column needs a name.'],
    ['N', [{ name: 'Gross Premium', terms: '' }, { name: 'gross-premium', terms: '' }], 'Column names must be unique: gross-premium.'],
    ['N', [{ name: '###', terms: '' }], '“###” is not a usable column name.'],
  ])('rejects %j', (name, rows, message) => {
    expect(validateFormat(name as string, rows as { name: string; terms: string }[]).errors).toContain(message);
  });
});

describe('FormatTemplateEditor', () => {
  it('builds a new format: name, columns and recognised terms', () => {
    const onSave = vi.fn();
    render(<FormatTemplateEditor busy={false} onSave={onSave} onCancel={() => {}} />);
    fireEvent.change(screen.getByLabelText(/Format name/), { target: { value: 'My format' } });
    fireEvent.change(screen.getByLabelText('Column name 1'), { target: { value: 'UMR' } });
    fireEvent.click(screen.getByRole('button', { name: 'Add column' }));
    fireEvent.change(screen.getByLabelText('Column name 2'), { target: { value: 'Premium Due' } });
    fireEvent.change(screen.getByLabelText('Recognised terms for Premium Due'), { target: { value: 'GWP\nPrime Brute' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save format' }));
    expect(onSave).toHaveBeenCalledWith({
      name: 'My format',
      columns: [
        { name: 'UMR', terms: [] },
        { name: 'Premium Due', terms: ['GWP', 'Prime Brute'] },
      ],
    });
  });

  it('changes an existing format: rename, remove a column, edit terms, add a column', () => {
    const onSave = vi.fn();
    render(<FormatTemplateEditor initial={lloyds} busy={false} onSave={onSave} onCancel={() => {}} />);
    expect(screen.getByRole('heading', { name: 'Change format' })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/Format name/), { target: { value: 'Lloyds V2' } });
    fireEvent.change(screen.getByLabelText('Column name 1'), { target: { value: 'Unique Market Ref' } });
    fireEvent.change(screen.getByLabelText('Recognised terms for Premium Due'), { target: { value: 'Prime Brute' } });
    fireEvent.click(screen.getByRole('button', { name: 'Add column' }));
    fireEvent.change(screen.getByLabelText('Column name 3'), { target: { value: 'Commission' } });
    fireEvent.click(screen.getByRole('button', { name: 'Remove column Unique Market Ref' }));
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }));
    expect(onSave).toHaveBeenCalledWith({
      name: 'Lloyds V2',
      columns: [
        { name: 'Premium Due', terms: ['Prime Brute'] },
        { name: 'Commission', terms: [] },
      ],
    });
  });

  it('shows what is wrong instead of saving', () => {
    const onSave = vi.fn();
    render(<FormatTemplateEditor busy={false} onSave={onSave} onCancel={() => {}} />);
    fireEvent.click(screen.getByRole('button', { name: 'Save format' }));
    expect(onSave).not.toHaveBeenCalled();
    const alert = screen.getByRole('alert');
    expect(alert).toHaveTextContent('Give the format a name.');
    expect(alert).toHaveTextContent('Add at least one column.');
  });

  it('removing the only column leaves one empty row rather than none', () => {
    render(<FormatTemplateEditor initial={acord} busy={false} onSave={() => {}} onCancel={() => {}} />);
    fireEvent.click(screen.getByRole('button', { name: 'Remove column Policy' }));
    expect((screen.getByLabelText('Column name 1') as HTMLInputElement).value).toBe('');
  });

  it('loads columns and terms from a file, replacing the rows', async () => {
    const parse = vi
      .spyOn(api.formats, 'parseFile')
      .mockResolvedValue({ columns: ['UMR', 'Premium Due'], terms: { 'Premium Due': ['GWP', 'Prime Brute'] }, skipped_terms: 2 });
    render(<FormatTemplateEditor initial={acord} busy={false} onSave={() => {}} onCancel={() => {}} />);
    const file = new File(['x'], 'f.csv', { type: 'text/csv' });
    fireEvent.change(screen.getByLabelText('Load columns and recognised terms from a file'), { target: { files: [file] } });
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Loaded 2 column(s) and 2 recognised term(s)'));
    expect(screen.getByRole('status')).toHaveTextContent('2 term(s) under an empty header were ignored');
    expect(parse).toHaveBeenCalledWith(file);
    expect((screen.getByLabelText('Column name 1') as HTMLInputElement).value).toBe('UMR');
    expect((screen.getByLabelText('Recognised terms for Premium Due') as HTMLTextAreaElement).value).toBe('GWP\nPrime Brute');
    expect(screen.queryByLabelText('Column name 3')).not.toBeInTheDocument();
  });

  it('shows a file problem and keeps the rows', async () => {
    vi.spyOn(api.formats, 'parseFile').mockResolvedValue({ columns: [], terms: {}, skipped_terms: 0 });
    render(<FormatTemplateEditor initial={acord} busy={false} onSave={() => {}} onCancel={() => {}} />);
    fireEvent.change(screen.getByLabelText('Load columns and recognised terms from a file'), {
      target: { files: [new File([''], 'e.csv')] },
    });
    expect(await screen.findByRole('alert')).toHaveTextContent('No column headers were found');
    expect((screen.getByLabelText('Column name 1') as HTMLInputElement).value).toBe('Policy');
  });
});

describe('FormatTemplateDirectory', () => {
  beforeEach(() => {
    vi.spyOn(api.formats, 'list').mockResolvedValue([lloyds, acord]);
  });

  it('lists the saved formats with their columns and terms', async () => {
    setAuthToken('dev-viewer1-viewer');
    renderWith(<FormatTemplateDirectory />);
    const list = await screen.findByRole('list', { name: 'Final formats' });
    expect(within(list).getByText("Lloyd's Standard")).toBeInTheDocument();
    expect(within(list).getByText('2 column(s) · 2 recognised term(s) · updated ' + new Date('2026-10-01T00:00:00Z').toLocaleDateString())).toBeInTheDocument();
    expect(within(list).getByText(/GWP, Prime Brute/)).toBeInTheDocument();
  });

  it('is read-only for roles that cannot change formats', async () => {
    setAuthToken('dev-viewer1-viewer');
    renderWith(<FormatTemplateDirectory />);
    await screen.findByText('ACORD');
    expect(screen.queryByRole('button', { name: 'New format' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Change format/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Remove format/ })).not.toBeInTheDocument();
    expect(screen.getByText('Your role can use saved formats but not change them.')).toBeInTheDocument();
  });

  it('adds a new format', async () => {
    setAuthToken('dev-analyst1-analyst');
    const create = vi.spyOn(api.formats, 'create').mockResolvedValue({ ...acord, id: 'f3', name: 'Fresh' });
    renderWith(<FormatTemplateDirectory />);
    await screen.findByText('ACORD');
    fireEvent.click(screen.getByRole('button', { name: 'New format' }));
    fireEvent.change(screen.getByLabelText(/Format name/), { target: { value: 'Fresh' } });
    fireEvent.change(screen.getByLabelText('Column name 1'), { target: { value: 'Policy' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save format' }));
    await waitFor(() => expect(create).toHaveBeenCalledWith({ name: 'Fresh', columns: [{ name: 'Policy', terms: [] }] }));
    await waitFor(() => expect(screen.queryByRole('form', { name: 'New format' })).not.toBeInTheDocument());
  });

  it('changes an existing format by id', async () => {
    setAuthToken('dev-analyst1-analyst');
    const update = vi.spyOn(api.formats, 'update').mockResolvedValue(lloyds);
    renderWith(<FormatTemplateDirectory />);
    fireEvent.click(await screen.findByRole('button', { name: "Format actions for Lloyd's Standard" }));
    fireEvent.click(await screen.findByRole('button', { name: "Change format Lloyd's Standard" }));
    fireEvent.change(screen.getByLabelText(/Format name/), { target: { value: 'Renamed' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }));
    await waitFor(() =>
      expect(update).toHaveBeenCalledWith('f1', { name: 'Renamed', columns: lloyds.columns }),
    );
  });

  it("shows the server's complaint (e.g. a name clash) and keeps the editor open", async () => {
    setAuthToken('dev-analyst1-analyst');
    vi.spyOn(api.formats, 'create').mockRejectedValue(new Error("A format named 'ACORD' already exists"));
    renderWith(<FormatTemplateDirectory />);
    await screen.findByText('ACORD');
    fireEvent.click(screen.getByRole('button', { name: 'New format' }));
    fireEvent.change(screen.getByLabelText(/Format name/), { target: { value: 'acord' } });
    fireEvent.change(screen.getByLabelText('Column name 1'), { target: { value: 'Policy' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save format' }));
    expect(await screen.findByText(/already exists/)).toBeInTheDocument();
    expect(screen.getByRole('form', { name: 'New format' })).toBeInTheDocument();
  });

  it('asks before removing a format, and can back out', async () => {
    setAuthToken('dev-analyst1-analyst');
    const remove = vi.spyOn(api.formats, 'remove').mockResolvedValue({ id: 'f2', deleted: true });
    renderWith(<FormatTemplateDirectory />);
    fireEvent.click(await screen.findByRole('button', { name: 'Format actions for ACORD' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Remove format ACORD' }));
    const confirm = screen.getByRole('alertdialog', { name: 'Remove ACORD?' });
    expect(confirm).toHaveTextContent('keep their own copy');
    fireEvent.click(within(confirm).getByRole('button', { name: 'Keep it' }));
    expect(remove).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Format actions for ACORD' }));
    fireEvent.click(screen.getByRole('button', { name: 'Remove format ACORD' }));
    fireEvent.click(within(screen.getByRole('alertdialog')).getByRole('button', { name: 'Remove format' }));
    await waitFor(() => expect(remove).toHaveBeenCalledWith('f2'));
  });

  it('invites the first format when the directory is empty', async () => {
    setAuthToken('dev-analyst1-analyst');
    vi.spyOn(api.formats, 'list').mockResolvedValue([]);
    renderWith(<FormatTemplateDirectory />);
    expect(await screen.findByText('No saved formats yet')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Add your first format' })).toBeInTheDocument();
  });
});
