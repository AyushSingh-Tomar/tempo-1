import { useState } from 'react';

export function SheetPicker({
  sheets,
  onConfirm,
  disabled,
}: {
  sheets: string[];
  onConfirm: (sheetName: string) => void;
  disabled?: boolean;
}) {
  const [selected, setSelected] = useState(sheets[0] ?? '');

  return (
    <div className="rounded-md border border-amber-200 bg-amber-50 p-4">
      <label htmlFor="sheet-select" className="block font-medium text-amber-900">
        This workbook has multiple worksheets. Choose one to continue.
      </label>
      <div className="mt-2 flex items-center gap-2">
        <select
          id="sheet-select"
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          className="rounded border border-amber-300 bg-white px-2 py-1.5"
        >
          {sheets.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <button
          type="button"
          disabled={disabled || !selected}
          onClick={() => onConfirm(selected)}
          className="rounded bg-amber-700 px-3 py-1.5 font-medium text-white hover:bg-amber-800 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-900"
        >
          Use this worksheet
        </button>
      </div>
    </div>
  );
}
