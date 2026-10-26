import { describe, expect, it, vi } from 'vitest';
import { useState } from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { RulesEditor, newRuleDraft } from '../src/components/reconciliation/RulesEditor';
import { EncodingPanel, FileCard } from '../src/components/reconciliation/FileCard';
import type { PreviewColumn, ReconFile } from '../src/api/reconTypes';
import type { RuleDraft } from '../src/utils/recon';

const bCols: PreviewColumn[] = [{ name: 'gross_premium', type: 'DECIMAL', derived: false }];
const sCols: PreviewColumn[] = [{ name: 'amount', type: 'DECIMAL', derived: false }];

function Harness() {
  const [rules, setRules] = useState<RuleDraft[]>([newRuleDraft(1)]);
  return <RulesEditor rules={rules} onChange={setRules} bordereauxColumns={bCols} subledgerColumns={sCols} />;
}

describe('RulesEditor token insertion', () => {
  it('inserts clicked columns and operators into the focused expression', () => {
    render(<Harness />);
    const box = screen.getByLabelText('Expression') as HTMLTextAreaElement;
    fireEvent.focus(box);
    fireEvent.click(screen.getByLabelText('Insert bordereaux.gross_premium'));
    fireEvent.click(screen.getByLabelText('Insert operator ='));
    fireEvent.click(screen.getByLabelText('Insert subledger.amount'));
    expect(box.value.replace(/\s+/g, ' ').trim()).toBe('bordereaux.gross_premium = subledger.amount');
    expect(screen.getByText(/Looks well-formed/)).toBeTruthy();
  });
});

const xlsx: ReconFile = {
  id: 'f1',
  filename: 'book.xlsx',
  format: 'XLSX',
  size_bytes: 2048,
  encoding: null,
  encoding_info: null,
  encoding_choice: null,
  sheets: ['A', 'B'],
  selected_sheets: [],
  header_row: 1,
  needs_sheet_choice: true,
};

describe('FileCard sheet choice', () => {
  it('flags that a sheet must be chosen and reports the selection', () => {
    const onPatch = vi.fn();
    render(<FileCard file={xlsx} options={[]} canEdit onPatch={onPatch} onRecheck={() => {}} onRemove={() => {}} />);
    expect(screen.getByRole('alert').textContent).toMatch(/Choose at least one sheet/);
    fireEvent.click(screen.getByLabelText('A'));
    expect(onPatch).toHaveBeenCalledWith({ selected_sheets: ['A'] });
  });

  it('disables editing for read-only roles', () => {
    render(<FileCard file={xlsx} options={[]} canEdit={false} onPatch={() => {}} onRecheck={() => {}} onRemove={() => {}} />);
    expect((screen.getByLabelText('A') as HTMLInputElement).disabled).toBe(true);
  });
});

describe('EncodingPanel', () => {
  const csv: ReconFile = { ...xlsx, id: 'f2', filename: 'a.csv', format: 'CSV', sheets: [], needs_sheet_choice: false, encoding: 'cp1252' };
  it('shows encoding, method, warnings and differing lines', () => {
    render(
      <EncodingPanel
        file={csv}
        options={[{ value: 'utf-8', label: 'UTF-8' }, { value: 'cp1252', label: 'Windows-1252' }]}
        canEdit
        onApply={() => {}}
        onRecheck={() => {}}
        info={{
          method: 'DETECTED',
          chosen: 'cp1252',
          all_agree: false,
          compared: ['utf-8', 'cp1252'],
          warnings: ['Possible mojibake'],
          differences: [{ line: 3, 'utf-8': 'Caf�', cp1252: 'Café' }],
          candidates: [{ encoding: 'cp1252', decodes_cleanly: true, replacement_chars: 0, control_chars: 0, mojibake_pairs: 0, score: 0.9 }],
        }}
      />,
    );
    expect(screen.getByText('cp1252', { selector: 'strong' })).toBeTruthy();
    expect(screen.getByText('DETECTED')).toBeTruthy();
    expect(screen.getByText('Possible mojibake')).toBeTruthy();
    expect(screen.getByText('Café')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Re-check encoding' })).toBeTruthy();
  });
});
