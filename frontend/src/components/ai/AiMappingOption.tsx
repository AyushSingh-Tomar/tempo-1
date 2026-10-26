import type { AiStatus } from '../../api/types';

/**
 * The "let AI help with ambiguous columns" control shown before mappings are generated.
 * Says plainly what will be sent, how long it can take, and what happens when AI is unavailable.
 */
export function AiMappingOption({
  status,
  loading,
  checked,
  onChange,
  disabled,
}: {
  status: AiStatus | undefined;
  loading: boolean;
  checked: boolean;
  onChange: (value: boolean) => void;
  disabled?: boolean;
}) {
  if (loading) return null;

  if (!status?.available) {
    return (
      <div className="rounded border border-slate-200 bg-slate-50 p-3 text-sm text-slate-600" role="note">
        <p className="font-medium text-slate-700">AI assistance is not available</p>
        <p className="mt-0.5">
          {status?.reason ?? 'AI could not be reached.'} Mapping will use the deterministic rules only - nothing is
          blocked.
        </p>
      </div>
    );
  }

  return (
    <label className="flex cursor-pointer items-start gap-3 rounded border border-violet-200 bg-violet-50 p-3 text-sm text-violet-900">
      <input
        type="checkbox"
        className="mt-1"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span>
        <span className="font-medium">Use AI to resolve ambiguous columns</span>
        <span className="mt-0.5 block text-violet-800">
          Columns the rules cannot settle (unknown headers, headers that fit several fields) are sent to{' '}
          {status.model ?? 'the AI model'} with their header, data type and a few sample values. This can take up to
          about {status.timeout_seconds}s. Answers are only suggestions - you approve every one - and if AI is slow or
          unavailable mapping simply continues without it.
        </span>
      </span>
    </label>
  );
}
