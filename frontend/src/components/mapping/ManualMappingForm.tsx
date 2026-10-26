import { useState } from 'react';
import type { TargetField } from '../../api/types';

/** Lets a reviewer assign a source column to any field of the selected target format. */
export function ManualMappingForm({
  sourceColumn,
  fields,
  onSubmit,
  disabled,
}: {
  sourceColumn: string;
  fields: TargetField[];
  onSubmit: (targetField: string) => void;
  disabled?: boolean;
}) {
  const [targetField, setTargetField] = useState('');
  const [open, setOpen] = useState(false);

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        disabled={disabled}
        className="text-sm font-medium text-slate-600 underline hover:text-slate-900 disabled:cursor-not-allowed disabled:opacity-50"
      >
        Map manually
      </button>
    );
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (targetField) {
          onSubmit(targetField);
          setOpen(false);
          setTargetField('');
        }
      }}
      className="flex flex-wrap items-center gap-2"
    >
      <label htmlFor={`manual-target-${sourceColumn}`} className="sr-only">
        Target field for {sourceColumn}
      </label>
      <select
        id={`manual-target-${sourceColumn}`}
        value={targetField}
        onChange={(e) => setTargetField(e.target.value)}
        className="w-48 rounded border border-slate-300 px-2 py-1 text-sm"
      >
        <option value="">Select a field...</option>
        <option value={`extra_${sourceColumn.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '') || 'column'}`}>
          (keep as extra column)
        </option>
        {fields.map((f) => (
          <option key={f.name} value={f.name}>
            {f.display_name}
            {f.required === 'mandatory' ? ' *' : ''}
          </option>
        ))}
      </select>
      <button
        type="submit"
        disabled={disabled || !targetField}
        className="rounded bg-slate-900 px-2 py-1 text-sm font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
      >
        Save
      </button>
      <button type="button" onClick={() => setOpen(false)} className="text-sm text-slate-500 hover:text-slate-700">
        Cancel
      </button>
    </form>
  );
}
