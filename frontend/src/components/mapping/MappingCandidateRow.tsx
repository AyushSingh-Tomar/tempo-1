import { useState } from 'react';
import type { MappingCandidate, TargetField } from '../../api/types';
import { ConfidenceBadge } from '../common/ConfidenceBadge';
import { StatusBadge } from '../common/StatusBadge';
import { AiTag } from '../ai/AiStatusBadge';
import { ManualMappingForm } from './ManualMappingForm';

function describeEvidence(e: MappingCandidate['evidence'][number]): string {
  if (e.description || e.message) return String(e.description ?? e.message);
  switch (e.type) {
    case 'alias_match':
      return e.stage === 'EXACT' && e.score === 1 ? 'Header is a data-dictionary term for this field' : `Header similarity ${Math.round((e.score ?? 0) * 100)}% (fuzzy)`;
    case 'duplicate_target_conflict':
      return e.winner ? 'Several columns match this field; this is the strongest' : 'Another column matches this field more strongly';
    case 'ambiguous_alias': {
      const names = Array.isArray(e.candidate_fields) ? (e.candidate_fields as string[]).join(', ') : '';
      return `Header is a term of several fields (${names})`;
    }
    case 'passthrough':
      return e.reason === 'mapping_rejected'
        ? 'Mapping rejected; column is carried through unchanged'
        : e.reason === 'numeric_no_dictionary_match'
          ? 'Numeric column with no dictionary match; checked against premium relationships after treaty figures'
          : 'No dictionary match; carried through unchanged';
    case 'manual_override':
      return 'Assigned manually by a reviewer';
    case 'llm_hint':
      return `AI hint: ${String(e.explanation ?? e.recommendation ?? '')}`;
    case 'ai_suggestion':
      return `AI suggests this field (${Math.round(Number(e.confidence ?? 0) * 100)}% sure): ${String(e.reason ?? '')}`;
    case 'ai_note':
      return `AI found no matching field: ${String(e.message ?? '')}`;
    case 'ai_preferred_other':
      return `AI preferred ${String(e.preferred ?? 'another field')} for this column`;
    default:
      return e.type ?? 'Evidence item';
  }
}

export function MappingCandidateRow({
  candidate,
  alternatives,
  fields,
  onApprove,
  onReject,
  onReopen,
  onManualMap,
  busyIds,
}: {
  candidate: MappingCandidate;
  alternatives: MappingCandidate[];
  fields: TargetField[];
  onApprove: (id: string) => void;
  onReject: (id: string, reason: string) => void;
  onReopen: (id: string) => void;
  onManualMap: (sourceColumn: string, targetField: string) => void;
  busyIds: Set<string>;
}) {
  const [showEvidence, setShowEvidence] = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const [showRejectForm, setShowRejectForm] = useState(false);
  const busy = busyIds.has(candidate.id);
  const isExtra = (candidate.target_field ?? '').startsWith('extra_');
  const isProposed = candidate.status === 'PROPOSED';
  const canReject = (isProposed || candidate.status === 'APPROVED') && !isExtra;
  const rejected = alternatives.filter((a) => a.status === 'REJECTED');
  const aiEvidence = (c: MappingCandidate) => c.evidence.find((e) => e.type === 'ai_suggestion');
  // An open AI proposal for this column (it may be the row itself or one of its alternatives).
  const aiProposal = [candidate, ...alternatives].find((c) => c.status === 'PROPOSED' && aiEvidence(c));
  const aiProposalEvidence = aiProposal ? aiEvidence(aiProposal) : undefined;
  const aiNote = candidate.evidence.find((e) => e.type === 'ai_note');

  return (
    <tr className="align-top">
      <td className="px-3 py-2 font-medium text-slate-800">{candidate.source_column}</td>
      <td className="px-3 py-2">
        {candidate.target_field ? (
          isExtra ? (
            <span className="text-slate-500" title="Carried through unchanged">
              {candidate.target_field} <span className="text-xs">(extra column)</span>
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5">
              {candidate.target_field}
              {aiEvidence(candidate) && <AiTag />}
            </span>
          )
        ) : (
          <span className="text-slate-400">(unmapped)</span>
        )}
        {aiNote && !aiProposal && (
          <p className="mt-1 max-w-xs text-xs text-violet-700">
            <AiTag title="AI looked at this column" /> {String(aiNote.message ?? 'No matching target field.')}
          </p>
        )}
      </td>
      <td className="px-3 py-2">
        {isExtra ? <span className="text-xs text-slate-400">n/a</span> : <ConfidenceBadge confidence={candidate.confidence} />}
      </td>
      <td className="px-3 py-2">
        {candidate.sample_values && candidate.sample_values.length > 0 ? (
          <ul className="space-y-0.5 text-xs text-slate-600">
            {candidate.sample_values.slice(0, 3).map((v, i) => (
              <li key={i} className="truncate font-mono">
                {String(v)}
              </li>
            ))}
          </ul>
        ) : (
          <span className="text-xs text-slate-400">n/a</span>
        )}
      </td>
      <td className="px-3 py-2">
        <StatusBadge value={candidate.status} />
        {aiProposal && aiProposalEvidence && (
          <div className="mt-1.5 max-w-xs rounded border border-violet-200 bg-violet-50 p-2 text-xs text-violet-900">
            <p>
              <AiTag /> suggests <span className="font-semibold">{aiProposal.target_field}</span>{' '}
              ({Math.round(Number(aiProposalEvidence.confidence ?? 0) * 100)}% sure)
            </p>
            {!!aiProposalEvidence.reason && <p className="mt-0.5 text-violet-800">{String(aiProposalEvidence.reason)}</p>}
            {aiProposal.id !== candidate.id && (
              <button
                type="button"
                disabled={busyIds.has(aiProposal.id)}
                onClick={() => onApprove(aiProposal.id)}
                className="mt-1 font-medium text-violet-900 underline disabled:opacity-50"
              >
                Use AI suggestion
              </button>
            )}
          </div>
        )}
        {rejected.map((r) => (
          <p key={r.id} className="mt-1 text-xs text-red-700">
            Rejected {r.target_field}
            {r.rejection_reason ? `: ${r.rejection_reason}` : ''}
          </p>
        ))}
      </td>
      <td className="px-3 py-2">
        <button
          type="button"
          onClick={() => setShowEvidence((s) => !s)}
          aria-expanded={showEvidence}
          className="text-xs font-medium text-slate-600 underline hover:text-slate-900"
        >
          {showEvidence ? 'Hide evidence' : 'Show evidence'}
          {alternatives.length > 0 ? ` (+${alternatives.length} alt.)` : ''}
        </button>
        {showEvidence && (
          <div className="mt-2 w-72 space-y-2 rounded border border-slate-200 bg-slate-50 p-2 text-xs">
            <div>
              <p className="font-semibold text-slate-600">Evidence</p>
              {candidate.evidence.length === 0 ? (
                <p className="text-slate-400">No evidence recorded.</p>
              ) : (
                <ul className="list-disc pl-4">
                  {candidate.evidence.map((e, i) => (
                    <li key={i}>{describeEvidence(e)}</li>
                  ))}
                </ul>
              )}
            </div>
            {alternatives.length > 0 && (
              <div>
                <p className="font-semibold text-slate-600">Other candidates</p>
                <ul className="space-y-1">
                  {alternatives.map((alt) => (
                    <li key={alt.id} className="flex items-center justify-between gap-2">
                      <span>
                        {alt.target_field ?? '(unmapped)'} - {Math.round((alt.confidence?.total ?? 0) * 100)}%{' '}
                        <span className="text-slate-500">({alt.status.toLowerCase()})</span>
                      </span>
                      {alt.status === 'REJECTED' && (
                        <button
                          type="button"
                          disabled={busyIds.has(alt.id)}
                          onClick={() => onReopen(alt.id)}
                          className="font-medium text-slate-700 underline disabled:opacity-50"
                        >
                          Reopen
                        </button>
                      )}
                      {alt.status === 'PROPOSED' && (
                        <button
                          type="button"
                          disabled={busyIds.has(alt.id)}
                          onClick={() => onApprove(alt.id)}
                          className="font-medium text-green-800 underline disabled:opacity-50"
                        >
                          Use this
                        </button>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </td>
      <td className="px-3 py-2 align-top">
        <div className="flex min-w-0 flex-col items-start gap-2">
          {isProposed && (
            <button
              type="button"
              onClick={() => onApprove(candidate.id)}
              disabled={busy}
              className="rounded bg-green-700 px-2 py-1 text-xs font-medium text-white hover:bg-green-800 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Approve
            </button>
          )}
          {candidate.status === 'REJECTED' && (
            <button
              type="button"
              onClick={() => onReopen(candidate.id)}
              disabled={busy}
              className="rounded border border-slate-300 px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-50"
            >
              Reopen
            </button>
          )}
          {canReject &&
            (!showRejectForm ? (
              <button
                type="button"
                onClick={() => setShowRejectForm(true)}
                disabled={busy}
                className="rounded border border-slate-300 px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isProposed ? 'Reject' : 'Unmap'}
              </button>
            ) : (
              <div className="flex flex-col gap-1">
                <label htmlFor={`reject-reason-${candidate.id}`} className="sr-only">
                  Reason for rejecting {candidate.source_column}
                </label>
                <input
                  id={`reject-reason-${candidate.id}`}
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                  placeholder="Reason (required)"
                  className="w-40 rounded border border-slate-300 px-2 py-1 text-xs"
                />
                <div className="flex gap-2">
                  <button
                    type="button"
                    disabled={busy || !rejectReason.trim()}
                    onClick={() => {
                      onReject(candidate.id, rejectReason.trim());
                      setShowRejectForm(false);
                      setRejectReason('');
                    }}
                    className="rounded bg-red-700 px-2 py-1 text-xs font-medium text-white hover:bg-red-800 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Confirm
                  </button>
                  <button type="button" onClick={() => setShowRejectForm(false)} className="text-xs text-slate-500 hover:text-slate-700">
                    Cancel
                  </button>
                </div>
                <p className="w-40 text-xs text-slate-500">The column will be kept as an extra column unless you map it elsewhere.</p>
              </div>
            ))}
          <ManualMappingForm
            sourceColumn={candidate.source_column}
            fields={fields}
            disabled={busy}
            onSubmit={(targetField) => onManualMap(candidate.source_column, targetField)}
          />
        </div>
      </td>
    </tr>
  );
}
