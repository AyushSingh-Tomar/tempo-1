import { useMemo, useState } from 'react';
import type { DiscrepancyFinding } from '../../api/types';
import { DataTable, type DataTableColumn } from '../common/DataTable';
import { StatusBadge } from '../common/StatusBadge';

type SortKey = 'severity' | 'affected_row_number' | 'variance';

export function DiscrepancyTable({
  findings,
  onSelect,
}: {
  findings: DiscrepancyFinding[];
  onSelect: (finding: DiscrepancyFinding) => void;
}) {
  const [severityFilter, setSeverityFilter] = useState('ALL');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [sortKey, setSortKey] = useState<SortKey>('severity');
  const [search, setSearch] = useState('');

  const severities = useMemo(() => Array.from(new Set(findings.map((f) => f.severity))), [findings]);
  const statuses = useMemo(() => Array.from(new Set(findings.map((f) => f.status))), [findings]);

  const filtered = useMemo(() => {
    let list = findings;
    if (severityFilter !== 'ALL') list = list.filter((f) => f.severity === severityFilter);
    if (statusFilter !== 'ALL') list = list.filter((f) => f.status === statusFilter);
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      list = list.filter(
        (f) =>
          f.message.toLowerCase().includes(q) ||
          f.check_id.toLowerCase().includes(q) ||
          (f.affected_field ?? '').toLowerCase().includes(q),
      );
    }
    const sorted = [...list].sort((a, b) => {
      if (sortKey === 'affected_row_number') return (a.affected_row_number ?? 0) - (b.affected_row_number ?? 0);
      if (sortKey === 'variance') return Math.abs(Number(b.variance ?? 0)) - Math.abs(Number(a.variance ?? 0));
      return String(a.severity).localeCompare(String(b.severity));
    });
    return sorted;
  }, [findings, severityFilter, statusFilter, search, sortKey]);

  const columns: DataTableColumn<DiscrepancyFinding>[] = [
    { key: 'check_id', header: 'Rule', render: (f) => f.check_id },
    { key: 'category', header: 'Category', render: (f) => f.category },
    { key: 'severity', header: 'Severity', render: (f) => <StatusBadge value={f.severity} /> },
    { key: 'status', header: 'Status', render: (f) => <StatusBadge value={f.status} /> },
    { key: 'row', header: 'Row', render: (f) => f.affected_row_number ?? 'n/a' },
    { key: 'field', header: 'Field', render: (f) => f.affected_field ?? 'n/a' },
    { key: 'expected', header: 'Expected', render: (f) => <span className="font-mono">{String(f.expected_value ?? '-')}</span> },
    { key: 'observed', header: 'Observed', render: (f) => <span className="font-mono">{String(f.observed_value ?? '-')}</span> },
    { key: 'variance', header: 'Variance', render: (f) => <span className="font-mono">{String(f.variance ?? '-')}</span> },
    { key: 'message', header: 'Explanation', render: (f) => <span className="text-xs">{f.message}</span> },
  ];

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end gap-3">
        <div>
          <label htmlFor="disc-search" className="block text-xs font-medium text-slate-600">
            Search
          </label>
          <input
            id="disc-search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="rule, field, message"
            className="rounded border border-slate-300 px-2 py-1 text-sm"
          />
        </div>
        <div>
          <label htmlFor="disc-severity" className="block text-xs font-medium text-slate-600">
            Severity
          </label>
          <select
            id="disc-severity"
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            className="rounded border border-slate-300 px-2 py-1 text-sm"
          >
            <option value="ALL">All</option>
            {severities.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="disc-status" className="block text-xs font-medium text-slate-600">
            Status
          </label>
          <select
            id="disc-status"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded border border-slate-300 px-2 py-1 text-sm"
          >
            <option value="ALL">All</option>
            {statuses.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="disc-sort" className="block text-xs font-medium text-slate-600">
            Sort by
          </label>
          <select
            id="disc-sort"
            value={sortKey}
            onChange={(e) => setSortKey(e.target.value as SortKey)}
            className="rounded border border-slate-300 px-2 py-1 text-sm"
          >
            <option value="severity">Severity</option>
            <option value="affected_row_number">Row</option>
            <option value="variance">Variance (largest first)</option>
          </select>
        </div>
      </div>

      {filtered.length === 0 ? (
        <p className="text-sm text-slate-500">No discrepancies match these filters.</p>
      ) : (
        <DataTable
          columns={columns}
          rows={filtered}
          rowKey={(f) => f.id}
          caption="Discrepancy findings"
          onRowClick={onSelect}
        />
      )}
    </div>
  );
}
