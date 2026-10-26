import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/endpoints';
import { describeError } from '../../api/errors';
import type { AiKeyTest, AiStatus } from '../../api/types';
import { aiStatusKey, useAiStatus } from '../../hooks/useAi';
import { AI_TONE_CLASSES, aiStatusMeta } from '../../utils/ai';
import { AiProgressBox } from '../ai/AiProgressBox';
import { AiStatusBadge } from '../ai/AiStatusBadge';

type Outcome =
  | { kind: 'saved'; test: AiKeyTest | null }
  | { kind: 'rejected'; test: AiKeyTest }
  | { kind: 'tested'; test: AiKeyTest }
  | { kind: 'removed' };

const TEST_TIMEOUT_SECONDS = 30;

function CurrentKey({ status }: { status: AiStatus }) {
  const source = status.key_source ?? 'none';
  const mine = status.user_key;
  let tone: 'success' | 'neutral' | 'warning' = 'neutral';
  let title = 'No API key - AI features are off';
  let detail = status.reason ?? 'Everything else in the app works without AI.';

  if (source === 'user' && mine?.configured) {
    tone = mine.validated_at ? 'success' : 'warning';
    title = `Using your API key ending in ${mine.hint}`;
    detail = mine.validated_at
      ? `Verified ${new Date(mine.validated_at).toLocaleString()}.`
      : 'Saved without a successful test - use "Test key" to check that it works.';
  } else if (source === 'server') {
    tone = 'success';
    title = "Using the application's shared API key";
    detail = 'Add your own key below to use it instead.';
  }
  const t = AI_TONE_CLASSES[tone];
  return (
    <div className={`rounded-md border p-3 text-sm ${t.box}`} role="status" aria-label="Current AI key">
      <p className="font-medium">{title}</p>
      <p className="mt-0.5">{detail}</p>
      {status.model && (
        <p className="mt-1 text-xs opacity-80">
          Model {status.model}
          {status.provider ? ` via ${status.provider}` : ''}
        </p>
      )}
    </div>
  );
}

function OutcomeNotice({ outcome, onSaveUntested }: { outcome: Outcome; onSaveUntested?: () => void }) {
  if (outcome.kind === 'removed') {
    return (
      <p role="status" className="rounded-md border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
        Your key was removed.
      </p>
    );
  }
  const ok = outcome.test?.status === 'ok';
  const meta = aiStatusMeta(outcome.test?.status ?? 'ok');
  const tone = AI_TONE_CLASSES[ok ? 'success' : meta.tone];
  const headline =
    outcome.kind === 'saved'
      ? ok
        ? 'Key verified and saved. AI features now use it.'
        : 'Key saved without a test.'
      : outcome.kind === 'rejected'
        ? 'Key not saved.'
        : ok
          ? 'The key works.'
          : 'The key could not be verified.';
  return (
    <div role={ok ? 'status' : 'alert'} className={`rounded-md border p-3 text-sm ${tone.box}`}>
      <div className="flex flex-wrap items-center gap-2">
        <p className="font-medium">{headline}</p>
        {outcome.test && <AiStatusBadge status={outcome.test.status} />}
      </div>
      {outcome.test && !ok && <p className="mt-1">{outcome.test.message}</p>}
      {outcome.kind === 'rejected' && onSaveUntested && meta.retriable && (
        <p className="mt-2">
          The provider could not be reached to check the key.{' '}
          <button type="button" onClick={onSaveUntested} className="font-medium underline">
            Save it without testing
          </button>
        </p>
      )}
    </div>
  );
}

/** Settings -> AI connection: give the app your own API key. Write-only; verified before it is saved. */
export function AiConnectionSection() {
  const queryClient = useQueryClient();
  const statusQuery = useAiStatus();
  const [value, setValue] = useState('');
  const [reveal, setReveal] = useState(false);
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmRemove, setConfirmRemove] = useState(false);

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: aiStatusKey });
    void queryClient.invalidateQueries({ queryKey: ['ai-activity'] });
  };

  const save = useMutation({
    mutationFn: (skipTest: boolean) => api.ai.myKey.save(value, { skipTest }),
    onSuccess: (r) => {
      setError(null);
      if (r.saved) {
        setValue('');
        setReveal(false);
        setOutcome({ kind: 'saved', test: r.test });
      } else if (r.test) {
        setOutcome({ kind: 'rejected', test: r.test });
      }
      refresh();
    },
    onError: (err) => {
      setOutcome(null);
      setError(describeError(err));
    },
  });
  const test = useMutation({
    mutationFn: () => api.ai.myKey.test(),
    onSuccess: (r) => {
      setError(null);
      setOutcome({ kind: 'tested', test: r.test });
      refresh();
    },
    onError: (err) => setError(describeError(err)),
  });
  const remove = useMutation({
    mutationFn: () => api.ai.myKey.remove(),
    onSuccess: () => {
      setConfirmRemove(false);
      setError(null);
      setOutcome({ kind: 'removed' });
      refresh();
    },
    onError: (err) => setError(describeError(err)),
  });

  const status = statusQuery.data;
  const hasOwnKey = !!status?.user_key?.configured;
  const busy = save.isPending || test.isPending || remove.isPending;
  const canSubmit = value.trim().length > 0 && !busy;

  return (
    <section aria-labelledby="ai-connection-heading" className="space-y-4">
      <div>
        <h3 id="ai-connection-heading" className="text-base font-semibold text-slate-900">
          AI connection
        </h3>
        <p className="mt-1 text-sm text-slate-600">
          Give the app your own API key and it will use it for your AI-assisted column mapping and money-relation
          suggestions. AI stays optional: without a key the app works exactly as before.
        </p>
      </div>

      {statusQuery.isLoading && <p className="text-sm text-slate-500">Checking the current AI connection...</p>}
      {statusQuery.isError && (
        <p role="alert" className="text-sm text-red-700">
          Could not read the AI connection: {describeError(statusQuery.error)}
        </p>
      )}
      {status && <CurrentKey status={status} />}

      <form
        className="space-y-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (canSubmit) save.mutate(false);
        }}
        autoComplete="off"
      >
        <label htmlFor="ai-api-key" className="block text-sm font-medium text-slate-800">
          {hasOwnKey ? 'Replace your API key' : 'Your API key'}
        </label>
        <div className="flex gap-2">
          <input
            id="ai-api-key"
            name="ai-api-key"
            type={reveal ? 'text' : 'password'}
            value={value}
            onChange={(e) => {
              setValue(e.target.value);
              setOutcome(null);
            }}
            autoComplete="off"
            spellCheck={false}
            autoCapitalize="off"
            placeholder={hasOwnKey ? `•••• ${status?.user_key?.hint ?? ''}` : 'Paste your API key'}
            aria-describedby="ai-api-key-help"
            disabled={busy}
            className="min-w-0 flex-1 rounded border border-slate-300 px-3 py-2 font-mono text-sm disabled:bg-slate-100"
          />
          <button
            type="button"
            onClick={() => setReveal((r) => !r)}
            aria-pressed={reveal}
            className="rounded border border-slate-300 bg-white px-3 text-sm text-slate-700 hover:bg-slate-100"
          >
            {reveal ? 'Hide' : 'Show'}
          </button>
        </div>
        <p id="ai-api-key-help" className="text-xs text-slate-500">
          It is checked with a short test request before it is saved, stored encrypted on the server, used only for your
          own AI requests, and never shown again (only its last 4 characters).
        </p>
        <button
          type="submit"
          disabled={!canSubmit}
          className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {save.isPending ? 'Verifying...' : 'Verify and save'}
        </button>
      </form>

      {(save.isPending || test.isPending) && (
        <AiProgressBox
          title={save.isPending ? 'Verifying your API key' : 'Testing your API key'}
          detail="A short test request is sent to the AI provider."
          timeoutSeconds={TEST_TIMEOUT_SECONDS}
          model={status?.model}
        />
      )}
      {outcome && !busy && (
        <OutcomeNotice outcome={outcome} onSaveUntested={value ? () => save.mutate(true) : undefined} />
      )}
      {error && (
        <p role="alert" className="text-sm text-red-700">
          {error}
        </p>
      )}

      {hasOwnKey && (
        <div className="flex flex-wrap items-center gap-3 border-t border-slate-200 pt-3">
          <button
            type="button"
            onClick={() => test.mutate()}
            disabled={busy}
            className="rounded border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-100 disabled:opacity-50"
          >
            Test key
          </button>
          {!confirmRemove ? (
            <button
              type="button"
              onClick={() => setConfirmRemove(true)}
              disabled={busy}
              className="text-sm font-medium text-red-700 underline disabled:opacity-50"
            >
              Remove my key
            </button>
          ) : (
            <span className="flex items-center gap-2 text-sm">
              Remove it? AI will{' '}
              {status?.key_source === 'user' && status.reason == null ? 'fall back to the shared key (if any).' : 'stop.'}
              <button
                type="button"
                onClick={() => remove.mutate()}
                disabled={busy}
                className="rounded bg-red-700 px-3 py-1 text-white hover:bg-red-800 disabled:opacity-50"
              >
                Yes, remove
              </button>
              <button type="button" onClick={() => setConfirmRemove(false)} className="text-slate-600 underline">
                Cancel
              </button>
            </span>
          )}
        </div>
      )}
    </section>
  );
}
