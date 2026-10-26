import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { TargetFormatChooser, termsPayload } from '../src/components/mapping/TargetFormatChooser';
import { api } from '../src/api/endpoints';
import type { FormatTemplate, TargetFormat } from '../src/api/types';

afterEach(() => {
  vi.restoreAllMocks();
});

const savedFormats: FormatTemplate[] = [
  {
    id: 'f1',
    name: "Lloyd's Standard",
    columns: [
      { name: 'UMR', terms: [] },
      { name: 'Premium Due', terms: ['GWP', 'Prime Brute'] },
    ],
    column_count: 2,
    term_count: 2,
  },
  { id: 'f2', name: 'ACORD', columns: [{ name: 'Policy', terms: [] }], column_count: 1, term_count: 0 },
];

const defaultFormat: TargetFormat = {
  mode: 'DEFAULT',
  selected: false,
  fields: [
    { name: 'gross_premium', display_name: 'Gross Premium (100%)', type: 'DECIMAL', required: 'mandatory', category: 'P', recognised_terms: ['GWP', 'Prem'], user_terms: [] },
  ],
};

function setup(formats: FormatTemplate[] = []) {
  vi.spyOn(api.mappings.targetFormat, 'get').mockResolvedValue(defaultFormat);
  vi.spyOn(api.formats, 'list').mockResolvedValue(formats);
  const onConfirm = vi.fn();
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <TargetFormatChooser runId="run-1" busy={false} onConfirm={onConfirm} />
    </QueryClientProvider>,
  );
  return onConfirm;
}

function chooseCustom(columns: string) {
  fireEvent.click(screen.getByLabelText(/Provide my own final columns/i));
  fireEvent.change(screen.getByLabelText('Target column names'), { target: { value: columns } });
}

describe('termsPayload', () => {
  it('keeps one term per non-empty line, only for columns still in the list', () => {
    expect(termsPayload(['A', 'B', 'C'], { A: ' GWP \n\nPrime Brute\r\n', B: '   ', Gone: 'x' })).toEqual({
      A: ['GWP', 'Prime Brute'],
    });
  });
});

describe('TargetFormatChooser', () => {
  it('sends exactly what it always did for the default dictionary and for plain custom columns', async () => {
    const onConfirm = setup();
    await waitFor(() => expect(api.mappings.targetFormat.get).toHaveBeenCalled());
    fireEvent.click(screen.getByRole('button', { name: /Use this format and generate mappings/i }));
    expect(onConfirm).toHaveBeenLastCalledWith({ mode: 'DEFAULT' });

    chooseCustom('UMR\nGross Premium');
    fireEvent.click(screen.getByRole('button', { name: /Use this format and generate mappings/i }));
    expect(onConfirm).toHaveBeenLastCalledWith({ mode: 'CUSTOM', columns: ['UMR', 'Gross Premium'] });
  });

  it('sends the recognised terms typed for each custom column', () => {
    const onConfirm = setup();
    chooseCustom('UMR\nPremium Due');
    fireEvent.change(screen.getByLabelText('Recognised terms for Premium Due'), { target: { value: 'GWP\nPrime Brute' } });
    fireEvent.click(screen.getByRole('button', { name: /Use this format and generate mappings/i }));
    expect(onConfirm).toHaveBeenLastCalledWith({
      mode: 'CUSTOM',
      columns: ['UMR', 'Premium Due'],
      terms: { 'Premium Due': ['GWP', 'Prime Brute'] },
    });
  });

  it('fills the columns and their terms from an uploaded file', async () => {
    const parse = vi
      .spyOn(api.mappings.targetFormat, 'parseTermsFile')
      .mockResolvedValue({ columns: ['UMR', 'Premium Due'], terms: { 'Premium Due': ['GWP', 'Prime Brute'] }, skipped_terms: 1 });
    const onConfirm = setup();
    fireEvent.click(screen.getByLabelText(/Provide my own final columns/i));
    const file = new File(['UMR,Premium Due\n,GWP\n'], 'terms.csv', { type: 'text/csv' });
    fireEvent.change(screen.getByLabelText('Upload columns and recognised terms'), { target: { files: [file] } });
    await waitFor(() => expect(screen.getByRole('status').textContent).toContain('Read 2 column(s) and 2 recognised term(s)'));
    expect(screen.getByRole('status').textContent).toContain('1 term(s) under an empty header were ignored');
    expect(parse).toHaveBeenCalledWith('run-1', file);
    expect((screen.getByLabelText('Recognised terms for Premium Due') as HTMLTextAreaElement).value).toBe('GWP\nPrime Brute');
    fireEvent.click(screen.getByRole('button', { name: /Use this format and generate mappings/i }));
    expect(onConfirm).toHaveBeenLastCalledWith({
      mode: 'CUSTOM',
      columns: ['UMR', 'Premium Due'],
      terms: { 'Premium Due': ['GWP', 'Prime Brute'] },
    });
  });

  it('shows the file error and keeps what was typed', async () => {
    vi.spyOn(api.mappings.targetFormat, 'parseTermsFile').mockResolvedValue({ columns: [], terms: {}, skipped_terms: 0 });
    setup();
    chooseCustom('UMR');
    const file = new File([''], 'empty.csv', { type: 'text/csv' });
    fireEvent.change(screen.getByLabelText('Upload columns and recognised terms'), { target: { files: [file] } });
    await waitFor(() => expect(screen.getByRole('alert').textContent).toContain('No column headers were found'));
    expect((screen.getByLabelText('Target column names') as HTMLTextAreaElement).value).toBe('UMR');
  });

  it('lists the built-in recognised terms of the default columns', async () => {
    setup();
    fireEvent.click(await screen.findByText('Show default columns'));
    expect(screen.getByTitle('GWP, Prem')).toBeTruthy();
  });

  it('offers three options and keeps the default one selected', () => {
    setup(savedFormats);
    const radios = screen.getAllByRole('radio');
    expect(radios.map((r) => (r as HTMLInputElement).checked)).toEqual([true, false, false]);
    expect(screen.getByLabelText(/Use the default data dictionary/)).toBeChecked();
    expect(screen.getByLabelText(/Use a saved format/)).not.toBeChecked();
    expect(screen.getByLabelText(/Provide my own final columns/)).not.toBeChecked();
  });

  it('uses a saved format from the directory', async () => {
    const onConfirm = setup(savedFormats);
    fireEvent.click(screen.getByLabelText(/Use a saved format/));
    const confirm = screen.getByRole('button', { name: /Use this format and generate mappings/i });
    expect(confirm).toBeDisabled(); // nothing chosen yet

    const select = await screen.findByLabelText('Saved format');
    expect(screen.getAllByRole('option').map((o) => o.textContent)).toEqual([
      'Select a saved format…',
      "Lloyd's Standard (2 columns)",
      'ACORD (1 columns)',
    ]);
    fireEvent.change(select, { target: { value: 'f1' } });
    const preview = screen.getByRole('list', { name: 'Columns in the selected format' });
    expect(preview.textContent).toContain('UMR');
    expect(preview.textContent).toContain('GWP, Prime Brute');
    expect(confirm).toBeEnabled();
    fireEvent.click(confirm);
    expect(onConfirm).toHaveBeenLastCalledWith({ mode: 'CUSTOM', template_id: 'f1' });
  });

  it('says so when there are no saved formats, and cannot be confirmed', async () => {
    setup([]);
    fireEvent.click(screen.getByLabelText(/Use a saved format/));
    expect(await screen.findByText(/No saved formats yet/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Add one in the formats directory' })).toHaveAttribute('href', '/#formats');
    expect(screen.getByRole('button', { name: /Use this format and generate mappings/i })).toBeDisabled();
  });

  it('switching between the three options keeps each option working', async () => {
    const onConfirm = setup(savedFormats);
    fireEvent.click(screen.getByLabelText(/Use a saved format/));
    fireEvent.change(await screen.findByLabelText('Saved format'), { target: { value: 'f2' } });
    chooseCustom('UMR');
    fireEvent.click(screen.getByRole('button', { name: /Use this format and generate mappings/i }));
    expect(onConfirm).toHaveBeenLastCalledWith({ mode: 'CUSTOM', columns: ['UMR'] }); // custom, not the saved one
    fireEvent.click(screen.getByLabelText(/Use the default data dictionary/));
    fireEvent.click(screen.getByRole('button', { name: /Use this format and generate mappings/i }));
    expect(onConfirm).toHaveBeenLastCalledWith({ mode: 'DEFAULT' });
    fireEvent.click(screen.getByLabelText(/Use a saved format/));
    fireEvent.click(screen.getByRole('button', { name: /Use this format and generate mappings/i }));
    expect(onConfirm).toHaveBeenLastCalledWith({ mode: 'CUSTOM', template_id: 'f2' }); // the earlier pick is remembered
  });
});
