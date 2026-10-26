const COLOR_MAP: Record<string, string> = {
  // Run / general positive
  COMPLETED: 'bg-green-100 text-green-800',
  SUCCEEDED: 'bg-green-100 text-green-800',
  APPROVED: 'bg-green-100 text-green-800',
  OVERRIDDEN: 'bg-blue-100 text-blue-800',
  VALID_DIFFERENCE: 'bg-blue-100 text-blue-800',
  // In progress / neutral
  PENDING: 'bg-slate-100 text-slate-700',
  RUNNING: 'bg-amber-100 text-amber-800',
  PROPOSED: 'bg-slate-100 text-slate-700',
  WARNING: 'bg-amber-100 text-amber-800',
  UNRESOLVED: 'bg-amber-100 text-amber-800',
  // Negative
  FAILED: 'bg-red-100 text-red-800',
  REJECTED: 'bg-red-100 text-red-800',
  CANCELLED: 'bg-slate-200 text-slate-600',
  CONFIRMED_ERROR: 'bg-red-100 text-red-800',
  ERROR: 'bg-red-100 text-red-800',
  CRITICAL: 'bg-red-100 text-red-800',
  INFO: 'bg-slate-100 text-slate-700',
};

export function StatusBadge({ value }: { value: string | null | undefined }) {
  if (!value) return null;
  const classes = COLOR_MAP[value] ?? 'bg-slate-100 text-slate-700';
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${classes}`}>
      {value.replace(/_/g, ' ')}
    </span>
  );
}
